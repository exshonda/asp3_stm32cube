# 書込み・デバッグ・シリアルのツール操作（ST-LINK / NUCLEO）

動作確認済み環境: ST-LINK FW V3J17M10、STM32CubeProgrammer 2.22.0、
OpenOCD（ディストリ版）、gdb-multiarch。

> **Windows で gdb デバッグする場合は [gdb-debug-windows.md](gdb-debug-windows.md) を参照**
> （OpenOCD+arm-none-eabi-gdb、flash は `hbreak` 必須、ST-LINK_gdbserver は error 32 で不可）。
> 本書の OpenOCD+gdb 節は Linux（gdb-multiarch）向け。

## STM32_Programmer_CLI（書込み・オプションバイト）

CLI 実体の例（STM32Cube bundles 配下に入ることがある）:
`~/.local/share/stm32cube/bundles/programmer/<ver>/bin/STM32_Programmer_CLI`

```bash
STM32_Programmer_CLI -l                                   # プローブ列挙（ボード名も出る）
STM32_Programmer_CLI -c port=SWD reset=HWrst \
  -w build/Debug/H533.elf -v -rst                         # 書込み+verify+リセット
STM32_Programmer_CLI -c port=SWD reset=HWrst -rst         # リセットのみ
STM32_Programmer_CLI -c port=SWD -ob displ                # オプションバイト（TZEN 等）
```

- ELF パスは**絶対パス推奨**（cwd 依存の `File does not exist` を避ける）。
- **OpenOCD が動いていると `DEV_CONNECT_ERR`**（ST-LINK 排他）。先に止める。
- ST-LINK FW が古いと接続時に更新を求められることがある（GUI の
  STM32CubeProgrammer で更新可能）。

## シリアル（ST-LINK VCP）

```bash
stty -F /dev/ttyACM0 115200 cs8 -cstopb -parenb -echo -icrnl raw
cat /dev/ttyACM0                            # 受信
printf 'r' > /dev/ttyACM0                   # 送信（sample1: rot_rdq でタスク切替）
```

リセット直後の出力を取りたい時は、`cat` をバックグラウンドで先に開始してから
書込み/リセットする（開始前の出力は取れない）。

## OpenOCD + gdb-multiarch（デバッグの正攻法）

- ST-LINK_gdbserver（CubeCLT 同梱）は FW 要求で使えないことがある。
  OpenOCD が確実。
- ディストリの OpenOCD に `stm32h5x.cfg` が無くても、**汎用 cortex_m の最小 cfg
  で十分動く** → [../snippets/openocd-h5.cfg](../snippets/openocd-h5.cfg)

```bash
openocd -f openocd-h5.cfg            # gdb server :3333
gdb-multiarch -q build/Debug/H533.elf -ex "target extended-remote :3333"
```

主要 gdb/monitor コマンド:

```
monitor halt / monitor resume / monitor reset halt
monitor cortex_m vector_catch hard_err bus_err mm_err chk_err state_err nocp_err int_err
                                     # フォルトで自動停止（reset は入れない）
p/x *(unsigned int*)0xE000ED28       # CFSR
p/x *(unsigned int*)0xE000ED38       # BFAR
call target_fput_log('X')            # 関数のターゲット上実行（出力経路の単体テスト）
```

注意:
- gdb をバッチで使う時は最後に `detach`。**kill で中断するとターゲットが
  壊れた状態のまま走り偽フォルトを生む**（リセットして観測し直す）。
- vector_catch は OpenOCD の機能（`monitor` 経由）。接続エラー時は
  既存の openocd/gdb プロセス残骸を疑う（`pgrep -af openocd`）。

## testexec の回し方（機能テスト全件・実機）

外側リポジトリの `scripts/testexec_stm32.py` を使う（asp3_core の testexec.py は
asp3_core 単体 configure 前提のため実機 CubeMX 構成では使えない）:

```bash
python3 scripts/testexec_stm32.py --board nucleo_h563zi          # 標準36本
python3 scripts/testexec_stm32.py --board nucleo_h563zi sem1     # 単発
python3 scripts/testexec_stm32.py --rejudge                      # 保存ログ再判定のみ
# ログ: nucleo_*/sample1/build/TestExec/logs/<test>.{build,ninja,flash,serial}.log
```

判定は CI ランナー互換（PASS/SKIP マーカー・hrt1/dlynse の SPECIAL_SPEC）。
**期待される非PASS**（arm_m 規範どおり）: cpuexc1/cpuexc4=FAIL（上流 PRIMASK 特性、
asp3_core `docs/dev/issue-cpuexc-armm.md`）、cpuexc10=SKIP、int1=BUILD_FAIL
（target_test.h の INTNO1 未整備）。dlynse は実機較正テスト＝NG が出たら
`stm32cubemx.h` の `SIL_DLY_TIM1/2` を較正する（小さくすると遅延が伸びる安全側）。

## test_porting の回し方（実機 TAP）

```bash
cd nucleo_h563zi/sample1
CORE=$PWD/../../asp3/asp3_core
cmake --preset Debug -B build/TestPorting \
  -DASP3_APPLDIR=$CORE/test/porting -DASP3_APPLNAME=test_porting \
  -DASP3_EXTRA_APP_C_FILES=$CORE/test/porting/tap.c
cmake --build build/TestPorting
STM32_Programmer_CLI -c port=SWD reset=HWrst -w $PWD/build/TestPorting/H563ZI.elf -v -rst
cat /dev/ttyACM0     # 「1..6」「ok 1」〜「ok 6」「# 6/6 passed」を確認
```
