---
name: porting-asp3-to-stm32
description: TOPPERS/ASP3 を STM32（NUCLEO-H5系・STM32CubeMX + HAL + arm-none-eabi-gcc）の新しいボードに移植する手順と、CubeMX 生成環境特有の落とし穴（ベクタテーブル整列・TrustZone・リンカGC等）をまとめたガイド。新規 NUCLEO ボード対応、実機ブリングアップのデバッグ、ビルド・書込み・検証の作業で参照する。
---

# TOPPERS/ASP3 を STM32 ボードに移植する

このリポジトリ（`asp3_stm32cube`・旧 `stm32_vscode_asp`）は TOPPERS/ASP3 Core を STM32Cube HAL 環境で
動かすための移植層。NUCLEO-H563ZI / NUCLEO-H533RE（いずれも Cortex-M33）を実例として、
新規 STM32 ボード対応や実機ブリングアップに必要な作業をまとめる。

## このスキルが扱う作業

1. **新規ボード（例: NUCLEO-H723ZG）を ASP3 に追加する** → [checklists/new-board.md](checklists/new-board.md)
2. **実機で動かない時のデバッグ** → [checklists/bringup-debug.md](checklists/bringup-debug.md)
3. **CubeMX コード生成の運用** → [reference/cubemx-generation.md](reference/cubemx-generation.md)
4. **書込み・デバッグ・シリアルのツール操作** → [reference/flash-debug-tools.md](reference/flash-debug-tools.md)

## 重要な前提知識（最初に読む）

### 1. ディレクトリ構成

```
asp3_stm32cube/
├── asp3/
│   ├── asp3_core/                 # カーネル本体（git submodule・無変更が原則）
│   ├── arch/arm_m_gcc/
│   │   └── stm32h5xx_stm32cube/   # チップ層（H5共通・外側リポジトリ管理）
│   ├── target/
│   │   ├── stm32h563_nucleo/           # NUCLEO-H563ZI 用ターゲット依存部
│   │   └── stm32h533_nucleo/      # NUCLEO-H533RE 用ターゲット依存部
│   └── asp3_stm32cube.cmake     # glue（ASP3_TARGET_DIR/ASP3_CORE_DIR 解決）
├── nucleo_h563zi/sample1/         # CubeMX プロジェクト（H563ZI.ioc が正本）
└── nucleo_h533re/sample1/         # CubeMX プロジェクト（H533.ioc が正本）
    ├── H533.ioc                   # CubeMX 設定（コミット対象）
    ├── Core/                      # CubeMX 生成 + USER CODE（main.c はコミット対象）
    ├── Drivers/ cmake/ *.ld       # CubeMX 生成（.gitignore・再生成で復元）
    └── CMakeLists.txt             # アプリ統合（ASP3_TARGET / ASP3_APPLDIR）
```

新規ボード追加では `asp3/target/<新ターゲット>` と `nucleo_<新ボード>/sample1/` の
2 箇所をセットで用意する。SDK 固有部は外側リポジトリ管理、asp3_core は
`ASP3_TARGET_DIR` で受け入れる（Pico SDK / FSP 統合と同方針）。

### 2. CubeMX 生成ファイルとの付き合い方（最重要）

**CubeMX が再生成するファイル**（直接編集してはいけない）:
- `Drivers/`、`cmake/`（toolchain・stm32cubemx ライブラリ定義）
- `*.ld`（リンカスクリプト）、`CMakePresets.json`、`startup_stm32*.s`
- `Core/` の生成部分（**USER CODE BEGIN/END の間だけ編集可**＝再生成で保持される）

clone 直後は生成物が無くビルド不可。**GUI の CubeMX で .ioc を開いて
GENERATE CODE する**（ヘッドレスは不可。詳細と理由は
[reference/cubemx-generation.md](reference/cubemx-generation.md)）。

**`.ld` に依存する設定を足してはいけない**（再生成で消える）。配置や整列が
必要なものはソース側の attribute で解決する（下記ベクタテーブルが典型）。

### 3. 実機ブリングアップで踏んだ地雷（必読）

詳細は [reference/vector-vtor-pitfalls.md](reference/vector-vtor-pitfalls.md)。要点:

| # | 落とし穴 | 症状 | 対策（実装済みの形） |
|---|---|---|---|
| 1 | **ベクタテーブル整列違反**（VTOR 要件） | バナーは出るがタスク切替で BusFault／全く動かない | `target_kernel.py` がテーブルに `aligned(2^⌈log2(エントリ数×4)⌉)` を生成 |
| 2 | **TOPPERS_ENABLE_TRUSTZONE の流用** | EXC_RETURN=0xFFFFFFFD（Secure用）が仕様上不正に | TZEN 無効（出荷時）の H5 では定義しない（`arch.cmake`） |
| 3 | **target_fput_log が stdio 経由** | 低レベルログが一切出ない | USART レジスタ直接ポーリングで実装 |
| 4 | **ツールチェーンのグローバル `--gc-sections`** | cfg1_out で `TOPPERS_magic_number not found` | `target.cmake` の `ASP3_LINK_OPTIONS` に `-Wl,--no-gc-sections`（後勝ち） |
| 5 | **ICF（同一コード畳み込み）** | gdb/addr2line が無関係な関数（Error_Handler 等）を指す | バックトレースを鵜呑みにしない。レジスタ・CFSR を一次情報に |

### 4. ビルド

```bash
cd nucleo_h533re/sample1  # または nucleo_h563zi/sample1
cmake --preset Debug
cmake --build build/Debug # → build/Debug/H533.elf
```

アプリ（既定 sample1）の差し替えは asp3_core 標準の `-D` 機構が使える:

```bash
CORE=$PWD/../../asp3/asp3_core
cmake --preset Debug -B build/TestPorting \
  -DASP3_APPLDIR=$CORE/test/porting -DASP3_APPLNAME=test_porting \
  -DASP3_EXTRA_APP_C_FILES=$CORE/test/porting/tap.c
cmake --build build/TestPorting
```

### 5. 書込みと動作確認

```bash
STM32_Programmer_CLI -c port=SWD reset=HWrst -w build/Debug/H533.elf -v -rst
stty -F /dev/ttyACM0 115200 cs8 -cstopb -parenb -echo -icrnl raw
cat /dev/ttyACM0
```

最小チェック（sample1）:
1. バナー → `Sample program starts (exinf = 0).` → `task1 is running (NNN)`
2. `printf 'r' > /dev/ttyACM0` で task1→task2→task3 が切り替わればディスパッチ OK
3. 仕上げは **test_porting（TAP 6項目）** を書込み、`1..6` / `ok 1`〜`ok 6` を確認

ツールのパス・OpenOCD/gdb の使い方は
[reference/flash-debug-tools.md](reference/flash-debug-tools.md)。

---

## 参考

- 経緯・root cause 解析の正本: `asp3/asp3_core/docs/dev/stm32-integration.md`
- 動作確認済み: NUCLEO-H563ZI / NUCLEO-H533RE、CubeMX 6.17.0 + FW_H5 V1.6.0、
  arm-none-eabi-gcc 13.2.1、STM32CubeProgrammer 2.22.0
- 同型の移植スキル: [asp3_fsp](https://github.com/exshonda/asp3_fsp)（Renesas RA / FSP）、
  asp3_pico_sdk（Raspberry Pi Pico）
