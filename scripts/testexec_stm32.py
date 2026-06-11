#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  STM32 実機向け testexec ランナー
#
#  asp3_core の test/testexec.py は asp3_core 単体を configure する前提のため、
#  CubeMX 外側プロジェクト（nucleo_*）では使えない。本スクリプトは外側プロジェクト
#  を 1 テストずつ configure（-DASP3_APPLDIR/APPLNAME/APPCFGNAME 差し替え）→
#  build → STM32_Programmer_CLI で書込み → シリアル出力を判定する。
#
#  判定は CI ランナー（asp3_core scripts/ci/run_testexec.py）互換:
#    PASS    "All check points passed."（hrt1/dlynse は SPECIAL_SPEC の完走マーカ）
#    SKIP    "This test program is not necessary."
#    FAIL    "## "・"not ok " 行・"Unregistered Exception"・SPECIAL_SPEC の fail
#    TIMEOUT 期限内にいずれも出ない
#
#  --rejudge で（実行せず）保存済み serial ログのみ再判定する。
#
#  使い方:
#    scripts/testexec_stm32.py --board nucleo_h563zi [--port /dev/ttyACM0] [test ...]
#    テスト名省略時は標準機能テスト一式（拡張パッケージ・perf・arm_* は対象外）
#
import argparse
import os
import re
import select
import subprocess
import sys
import termios
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CORE = os.path.join(REPO, "asp3", "asp3_core")

PROGRAMMER = os.path.expanduser(
    "~/.local/share/stm32cube/bundles/programmer/2.22.0+st.1/bin/STM32_Programmer_CLI")

#  標準機能テスト（asp3_core test/testexec.py の TEST_SPEC から、
#  拡張パッケージ（messagebuf/ovrhdr/rstr/subprio/inherit）・perf・arm_* を除く）
TEST_SPEC = {
    **{f"cpuexc{i}": {"SRC": f"test_cpuexc{i}", "CFG": "test_cpuexc"}
       for i in range(1, 11)},
    "dlynse":   {"SRC": "test_dlynse"},
    "dtq1":     {"SRC": "test_dtq1"},
    "exttsk":   {"SRC": "test_exttsk"},
    "flg1":     {"SRC": "test_flg1"},
    "hrt1":     {"SRC": "test_hrt1"},
    "int1":     {"SRC": "test_int1"},
    "mpf1":     {"SRC": "test_mpf1"},
    **{f"mutex{i}": {"SRC": f"test_mutex{i}"} for i in range(1, 9)},
    "notify1":  {"SRC": "test_notify1"},
    "pdq1":     {"SRC": "test_pdq1"},
    "raster1":  {"SRC": "test_raster1"},
    "raster2":  {"SRC": "test_raster2"},
    "sem1":     {"SRC": "test_sem1"},
    "sem2":     {"SRC": "test_sem2"},
    "suspend1": {"SRC": "test_suspend1"},
    "sysman1":  {"SRC": "test_sysman1"},
    "sysstat1": {"SRC": "test_sysstat1"},
    "task1":    {"SRC": "test_task1"},
    "tmevt1":   {"SRC": "test_tmevt1"},
}


def run(cmd, log_path, timeout=300):
    with open(log_path, "w") as out:
        return subprocess.call(cmd, shell=True, timeout=timeout,
                               stdout=out, stderr=subprocess.STDOUT) == 0


def open_serial(port):
    fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0                       # raw
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL  # 8N1
    attrs[4] = attrs[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIFLUSH)
    return fd


#  判定マーカー（asp3_core scripts/ci/run_testexec.py と同一仕様）
PASS_MARK = "All check points passed."
SKIP_MARK = "This test program is not necessary."
FAIL_PATTERNS = (
    re.compile(r"^not ok "),
    re.compile(r"^## "),
    re.compile(r"^Unregistered (Exception|Interrupt)"),
)
SPECIAL_SPEC = {
    "hrt1": {
        "pass": "high resolution timer count test finishes.",
        "fail": (re.compile(r"goes back"),),
    },
    "dlynse": {
        "pass": "-- for checking boundary conditions --",
        "fail": (re.compile(r"sil_dly_nse\(\d+\): \d+ NG"),),
    },
}


def judge_text(test, text):
    special = SPECIAL_SPEC.get(test, {})
    pass_mark = special.get("pass", PASS_MARK)
    fail_patterns = FAIL_PATTERNS + special.get("fail", ())
    for line in text.splitlines():
        for pat in fail_patterns:
            if pat.search(line):
                return "FAIL", line.strip()
    if SKIP_MARK in text:
        return "SKIP", "not necessary on this target"
    if pass_mark in text:
        return "PASS", ""
    return None, ""


def judge_serial(test, fd, deadline, log_file):
    buf = b""
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.5)
        if not r:
            continue
        try:
            chunk = os.read(fd, 4096)
        except BlockingIOError:
            continue
        if not chunk:
            continue
        buf += chunk
        log_file.write(chunk)
        verdict, detail = judge_text(test, buf.decode("ascii", errors="replace"))
        if verdict:
            return verdict, detail
    return "TIMEOUT", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="nucleo_h563zi")
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--run-timeout", type=int, default=60)
    ap.add_argument("--rejudge", action="store_true",
                    help="実行せず保存済み serial ログのみ再判定")
    ap.add_argument("tests", nargs="*", default=list(TEST_SPEC))
    args = ap.parse_args()

    board_dir = os.path.join(REPO, args.board)
    build_dir = os.path.join(board_dir, "build", "TestExec")
    elf = None  # configure 後に *.elf を探す
    logs = os.path.join(build_dir, "logs")
    os.makedirs(logs, exist_ok=True)

    results = {}
    if args.rejudge:
        for test in args.tests:
            slog = os.path.join(logs, f"{test}.serial.log")
            if not os.path.isfile(slog):
                results[test] = ("NO_LOG", "")
                continue
            with open(slog, "rb") as f:
                text = f.read().decode("ascii", errors="replace")
            verdict, detail = judge_text(test, text)
            results[test] = (verdict or "TIMEOUT", detail)
        return summary(results)

    for test in args.tests:
        spec = TEST_SPEC.get(test)
        if spec is None:
            results[test] = ("SKIP", "unknown test name")
            continue
        applname = spec["SRC"]
        cfgname = spec.get("CFG", applname)
        print(f"== {test} ==", flush=True)

        cfg_cmd = (
            f"cmake --preset Debug -B {build_dir} "
            f"-DASP3_APPLDIR={CORE}/test "
            f"-DASP3_APPLNAME={applname} "
            f"-DASP3_APPCFGNAME={cfgname} "
            f"\"-DASP3_EXTRA_APP_C_FILES={CORE}/syssvc/test_svc.c\""
        )
        log = os.path.join(logs, f"{test}.build.log")
        if not (run(f"cd {board_dir} && {cfg_cmd}", log) and
                run(f"cmake --build {build_dir}", log.replace(".build.", ".ninja."))):
            results[test] = ("BUILD_FAIL", f"see {log}")
            print("   BUILD_FAIL", flush=True)
            continue

        if elf is None:
            elf = next(f for f in os.listdir(build_dir) if f.endswith(".elf"))
        elf_path = os.path.join(build_dir, elf)

        fd = open_serial(args.port)
        try:
            if not run(f"{PROGRAMMER} -c port=SWD reset=HWrst -w {elf_path} -v -rst",
                       os.path.join(logs, f"{test}.flash.log")):
                results[test] = ("FLASH_FAIL", "")
                print("   FLASH_FAIL", flush=True)
                continue
            with open(os.path.join(logs, f"{test}.serial.log"), "wb") as slog:
                verdict, detail = judge_serial(test, fd,
                                               time.time() + args.run_timeout, slog)
        finally:
            os.close(fd)
        results[test] = (verdict, detail)
        print(f"   {verdict} {detail}", flush=True)
    return summary(results)


def summary(results):
    print("\n==== summary ====")
    counts = {}
    for test, (verdict, detail) in results.items():
        counts[verdict] = counts.get(verdict, 0) + 1
        print(f"{verdict:10s} {test:10s} {detail}")
    print(", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
          f"/ total={len(results)}")
    return 0 if set(counts) <= {"PASS", "SKIP"} else 1


if __name__ == "__main__":
    sys.exit(main())
