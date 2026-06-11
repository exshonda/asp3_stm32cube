# 書込み・デバッグ・シリアルのツール操作（ST-LINK / NUCLEO）

動作確認済み環境: ST-LINK FW V3J17M10、STM32CubeProgrammer 2.22.0、
OpenOCD（ディストリ版）、gdb-multiarch。

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

## test_porting の回し方（実機 TAP）

```bash
cd nucleo_h563zi
CORE=$PWD/../asp3/asp3_core
cmake --preset Debug -B build/TestPorting \
  -DASP3_APPLDIR=$CORE/test/porting -DASP3_APPLNAME=test_porting \
  -DASP3_EXTRA_APP_C_FILES=$CORE/test/porting/tap.c
cmake --build build/TestPorting
STM32_Programmer_CLI -c port=SWD reset=HWrst -w $PWD/build/TestPorting/H563ZI.elf -v -rst
cat /dev/ttyACM0     # 「1..6」「ok 1」〜「ok 6」「# 6/6 passed」を確認
```
