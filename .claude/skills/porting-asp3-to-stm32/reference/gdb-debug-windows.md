# GDB デバッグ（Windows / NUCLEO-H5）

NUCLEO-H533RE / H563ZI を **Windows 上の CLI から `arm-none-eabi-gdb` で実機デバッグ**する手順。
**動作実証済み**（2026-06、NUCLEO-H533RE・sample1）。

> Linux 環境は [flash-debug-tools.md](flash-debug-tools.md) の OpenOCD + gdb-multiarch 節を参照。
> Windows では gdbserver に **OpenOCD を使う**（ST-LINK_gdbserver は本環境で `error 32` 不可。後述）。

---

## 0. 結論（要点）

| 項目 | 内容 |
|---|---|
| gdbserver | **OpenOCD**（最小 H5 cfg）。ポート `:3333` |
| gdb クライアント | arm-none-eabi gcc 同梱 `arm-none-eabi-gdb`（gdb-multiarch 不要） |
| **最重要の落とし穴** | **flash 上のブレークは `hbreak`（HW BP）必須**。`break`（ソフト BP）は flash に書けず**無音で発火せず `continue` が無限待ち**になる |
| 終了 | **必ず `detach`**。gdb を kill するとターゲットが halted のまま wedge し、次回 `continue` が固まる |
| ST-LINK_gdbserver | 本環境では `Target unknown error 32` で接続不可（OpenOCD で代替） |

---

## 1. ツール（このマシンでの実体パス）

```
OpenOCD            C:\sw\openocd_v0.12.0\bin\openocd.exe        # 0.12.0（stm32h5x.cfg は無い）
gdb                C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\13.2 Rel1\bin\arm-none-eabi-gdb.exe
STM32_Programmer_CLI  C:\sw\ST\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe   # 書込み・リセット用
```

OpenOCD 0.12.0 には `target/stm32h5x.cfg` が無いが、**汎用 cortex_m の最小 cfg で十分**。
→ [../snippets/openocd-h5-windows.cfg](../snippets/openocd-h5-windows.cfg)

> Windows 版 OpenOCD 0.12.0 は `interface/stlink.cfg`（hla）＋ `transport select swd` を
> 拒否する（`Debug adapter doesn't support 'swd' transport`）。
> **`interface/stlink-dap.cfg`（st-link＝DAP ドライバ）＋ `transport select dapdirect_swd`** を使う。
> Linux 用 [../snippets/openocd-h5.cfg](../snippets/openocd-h5.cfg) との唯一の違いはこの2行。

---

## 2. 手順

### 2-1. 書込み（未書込みなら）

```bash
STM32_Programmer_CLI -c port=SWD reset=HWrst -w build/Debug/H533.elf -v -rst
```

### 2-2. OpenOCD（gdbserver）をバックグラウンド起動

```bash
openocd -f openocd-h5-windows.cfg          # → "Listening on port 3333 for gdb connections"
```

`Cortex-M33 r0p4 processor detected` / `SWD DPIDR 0x6ba02477` が出れば接続成功。
OpenOCD は **probe を排他**するので、起動中は STM32_Programmer_CLI を使わない（`DEV_CONNECT_ERR`）。

### 2-3. gdb で接続・デバッグ

対話起動:

```bash
arm-none-eabi-gdb -q build/Debug/H533.elf
(gdb) target extended-remote :3333
(gdb) monitor halt
(gdb) hbreak sample1.c:172        # ★ flash は hbreak（break ではない）
(gdb) continue                    # → ブレークで停止
(gdb) backtrace
(gdb) info locals
(gdb) print n
(gdb) delete
(gdb) monitor resume
(gdb) detach                      # ★ 必ず detach。kill しない
(gdb) quit
```

バッチ（CI / 自動確認）:

```bash
arm-none-eabi-gdb -q -batch build/Debug/H533.elf -x dbg.gdb
```

`dbg.gdb` の例:

```
set pagination off
set confirm off
target extended-remote :3333
monitor halt
hbreak sample1.c:172
continue
backtrace
info locals
print n
delete
monitor resume
detach
quit
```

---

## 3. 動作実証ログ（NUCLEO-H533RE・sample1）

```
Hardware assisted breakpoint 1 at 0x800795c: file .../sample/sample1.c, line 172.
Breakpoint 1, task (exinf=1) at .../sample1.c:172
#0  task (exinf=1) at .../sample1.c:172
#1  0x0800a998 in dly_tsk (dlytim=0) at .../kernel/task_sync.c:479
  exinf = 1,  n = 21,  tskno = 1,  graph = {"|", "  +", "    *"}
（continue 2回目）n = 22        ← カウンタ増加＝実行継続を確認
[Inferior 1 (Remote target) detached]
```

主要 monitor コマンド（OpenOCD 機能）:

```
monitor halt / monitor resume
monitor reg pc
monitor cortex_m vector_catch hard_err bus_err mm_err chk_err state_err nocp_err int_err
p/x *(unsigned int*)0xE000ED28       # CFSR
p/x *(unsigned int*)0xE000ED38       # BFAR
```

---

## 4. 踏んだ地雷（必読）

| # | 症状 | 原因 | 対策 |
|---|---|---|---|
| 1 | `break` を張って `continue` すると**永遠に停止しない** | 最小 cfg に **flash bank 定義が無い** → gdb がソフト BP を flash に書こうとして無音で失敗、BP が発火しない | **`hbreak`（Cortex-M FPB のHW BP）を使う**。H5 は HW BP 8本 |
| 2 | 2回目以降の接続で `continue` が即固まる／同じ PC で frozen | 前回 gdb を **kill で中断**し detach しなかった → コアが halted のまま wedge | **必ず `detach`**。wedge したら `STM32_Programmer_CLI -c port=SWD reset=HWrst -rst` で復帰 |
| 3 | `monitor reset halt` 後に動かない | 汎用 cfg の reset は **SYSRESETREQ**（`VECTRESET is not supported`）でフラッシュ起動シーケンスを正しく踏めない | reset halt に頼らず、**動作中のターゲットへ attach → `monitor halt`** で止める。リセットが要るなら programmer の HWrst を使う |
| 4 | OpenOCD 起動で `Debug adapter doesn't support 'swd' transport` | Windows OpenOCD 0.12.0 の hla ドライバが swd 非対応 | `stlink-dap.cfg` ＋ `transport select dapdirect_swd`（[snippet](../snippets/openocd-h5-windows.cfg)） |
| 5 | gdb 起動時に `could not convert '' from CP1252` 警告 | Windows ロケールの無害な警告 | 無視可（出力には影響なし） |

---

## 5. ST-LINK_gdbserver が使えない（既知の問題・error 32）

ST 純正の **ST-LINK_gdbserver（UM3088 §4.1 の正規手順）は本環境で接続不可**。
`STM32_Programmer_CLI` と OpenOCD は同じ probe で正常接続できるのに、gdbserver だけが失敗する。

```
Target connection failed   （24MHz〜5kHz の全速度、default / under-reset すべて）
Target unknown error 32
Error in initializing ST-LINK device.
```

### 試して **すべて NG** だった項目（再挑戦時の無駄打ち防止）

- gdbserver 2 版（CubeIDE 同梱 **7.13.0** / CubeCLT 1.18.0 **7.10.0**）
- 直結モード / `-t` 共有モード（システム `stlink_server v2.1.1` 起動）
- `-cp` を standalone / CubeIDE 同梱の両 CubeProgrammer に（DLL 一致）
- `-k`（init under reset）・`-m 0`（core 選択）・`-g`（attach）の有無
- **UM3088 §4.1 の正規コマンドそのまま**：`ST-LINK_gdbserver -d -v -t -cp <…\STM32CubeProgrammer\bin>`
- ボードの USB 抜き差し
- **ST-LINK FW 3 版（V3J17M10 / V3J16M7 / V3J16M8）** → FW 非依存と確定

### 切り分けの結論

- ターゲット・ST-LINK・SWD は健全（**OpenOCD で DPIDR 読取・halt 成功、CubeProgrammer で UR 接続・書込み成功**）。
- 直結モードでも `STLinkUSBDriver.dll`（`-cp` 経由）で失敗する。同じ DLL を使う CubeProgrammer は成功するので、
  **ST-LINK_gdbserver 固有の環境問題**（Windows の ST-LINK USB ドライバ/列挙、または 2023 年版 stlink_server と
  2025/2026 年版 gdbserver のプロトコル不整合が疑わしい）。
- **回避策＝OpenOCD を gdbserver にする**（本書 §2）。gdb クライアントの操作・体験は ST gdbserver と同一。

### 未消化の手（どうしても ST gdbserver を使いたい場合）

1. STM32CubeProgrammer GUI で **ST-LINK USB ドライバを再インストール**してから再試行。
2. `stlink_server` を gdbserver と同世代（CubeCLT 同梱版）に更新。
3. CubeIDE GUI のデバッガで接続できるか切り分け（GUI は内部で別の接続シーケンスを使う）。

> ⚠️ **FW 注意**：上記切り分け中に `STLinkUpgrade -force_prog` で ST-LINK FW を
> `V3J17M10` → `V3J16M8` に**ダウングレード**した（CLI 同梱ツールには J16 系の像しか無く、
> **CLI では J17M10 に戻せない**）。実機動作・OpenOCD デバッグには影響なし。
> J17M10 へ戻すには STM32CubeProgrammer GUI（ST から最新 FW を取得）でのアップグレードが必要。
