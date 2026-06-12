# 実機検証の状況と再実行手順（2026-06-12 時点）

NUCLEO-H533RE / NUCLEO-H563ZI の実機検証スナップショット。
経緯・root cause 解析の正本は `asp3/asp3_core/docs/dev/stm32-integration.md`、
作業ガイド（ビルド・書込み・デバッグの詳細）は
`.claude/skills/porting-asp3-to-stm32/` を参照。

## 検証結果サマリ

| 項目 | NUCLEO-H533RE | NUCLEO-H563ZI |
|---|---|---|
| sample1（バナー・タスク切替 `r`） | OK | OK |
| test_porting（TAP 6項目） | **6/6** | **6/6** |
| testexec（機能テスト36本） | **PASS=32 / SKIP=1 / FAIL=2 / BUILD_FAIL=1** | 同一 |

環境：CubeMX 6.17.0 + FW_H5 V1.6.0／arm-none-eabi-gcc 13.2.1／
STM32CubeProgrammer 2.22.0／ST-LINK FW V3J17M10。

### testexec の非PASS 内訳（両ボード共通・すべて既知）

| テスト | 判定 | 理由 |
|---|---|---|
| cpuexc1・cpuexc4 | FAIL | 上流 arm_m 固有の特性（PRIMASK SIL 中の UsageFault が HardFault 昇格）。mps2/pico2_arm と同一挙動。`asp3_core docs/dev/issue-cpuexc-armm.md` |
| cpuexc10 | SKIP | `This test program is not necessary.`（このターゲット構成では不要＝正常） |
| int1 | BUILD_FAIL | `target_test.h` にテスト用ソフト割込み源（INTNO1）未整備（`docs/TODO.md` §2） |

特記：**hrt1・dlynse は QEMU CI では検証不能な実機専用テストで、両ボードとも PASS**。
dlynse は H563ZI の実測に基づき `SIL_DLY_TIM1` を 79→64 に較正済み
（`asp3/target/*/stm32cubemx.h`。クロック構成の異なる H533RE でも NG 0件を確認）。

## 再実行手順

```bash
# 前提：CubeMX で .ioc を GENERATE CODE 済み（clone 直後は生成物が無い）

# sample1（既定アプリ）
cd nucleo_h533re && cmake --preset Debug && cmake --build build/Debug
STM32_Programmer_CLI -c port=SWD reset=HWrst -w build/Debug/H533.elf -v -rst

# test_porting（TAP 6項目）
CORE=$PWD/../asp3/asp3_core
cmake --preset Debug -B build/TestPorting \
  -DASP3_APPLDIR=$CORE/test/porting -DASP3_APPLNAME=test_porting \
  -DASP3_EXTRA_APP_C_FILES=$CORE/test/porting/tap.c
cmake --build build/TestPorting
# 書込み後、シリアル(/dev/ttyACM0 115200)で「1..6」「ok 1〜6」を確認

# testexec（機能テスト全件・リポジトリルートで）
python3 scripts/testexec_stm32.py --board nucleo_h533re        # 全36本（約40分）
python3 scripts/testexec_stm32.py --board nucleo_h533re sem1   # 単発
python3 scripts/testexec_stm32.py --rejudge                    # 保存ログ再判定のみ
# ログ: nucleo_*/build/TestExec/logs/<test>.{build,ninja,flash,serial}.log
```

判定は asp3_core の CI ランナー（`scripts/ci/run_testexec.py`）と同一仕様
（PASS/SKIP マーカー・hrt1/dlynse の個別マーカー判定）。
