# 新規 STM32 ボード追加チェックリスト

新しい NUCLEO ボード（例: NUCLEO-H723ZG）に TOPPERS/ASP3 を追加するときの作業手順。
実例: NUCLEO-H533RE 追加（`target/stm32cubemx`＝H563ZI を複製して最小改変）。

## 事前準備

- [ ] CubeMX（現行版）にボードの FW パッケージが入るか確認（generate 時に自動 DL 可）
- [ ] ボードの VCP（ST-LINK Virtual COM Port）がどの USART/ピンかをボードマニュアルで確認
      （例: H563ZI=USART3/PD8-9、H533RE=USART2/PA2-3）
- [ ] 同系チップ（同じ `arch/arm_m_gcc/<chip>` 層が使えるか）を確認。
      H5 系なら `stm32h5xx_stm32cube` がそのまま使える。別系列（H7 等）はチップ層の複製も必要

## CubeMX プロジェクト（`nucleo_<新ボード>/`）

- [ ] CubeMX で Board Selector から新ボードを選び、既存 `.ioc` と同等の設定で作成:
  - Toolchain: **CMake**
  - VCP の USART を Asynchronous 115200 で有効化（割込みも有効に）
  - TIM2（HRT）＋TIM5（割込みタイマ）を既存 ioc と同設定で有効化
  - SysTick は HAL 既定のまま（カーネルは TIM を使う＝`USE_TIM_AS_HRT`）
- [ ] GENERATE CODE → `Core/ Drivers/ cmake/ *.ld CMakePresets.json` が生成される
- [ ] `Core/Src/main.c` の USER CODE 内に追記（再生成で保持される）:
  ```c
  /* USER CODE BEGIN Includes */
  #include "target_kernel.h"
  /* USER CODE END Includes */
  ...（main の while(1) 直前）
  /* USER CODE BEGIN 2 */
  sta_ker();
  /* USER CODE END 2 */
  ```
- [ ] `CMakeLists.txt` を既存ボードからコピーして編集:
  - `ASP3_TARGET` を新ターゲット名に
  - アプリ選択（`ASP3_APPLDIR`/`ASP3_APPLNAME`）の `if(NOT DEFINED)` ガードを維持
    （test_porting 差し替えに必要）
- [ ] `.gitignore` の生成物パターンが新ディレクトリにも効いているか確認

## ASP3 ターゲット依存部（`asp3/target/<新ターゲット>/`）

既存ボード（`stm32h533_nucleo` か `stm32cubemx`）をディレクトリごとコピーして編集。

- [ ] `target.cmake` — チップ define（`STM32H533xx` 等）・コメント
- [ ] `target_stddef.h` — `TOPPERS_NUCLEO_*` マクロ
- [ ] `target_syssvc.h` — `TARGET_NAME`（バナー表記）
- [ ] `target_serial.h` — `INHNO_USART/INTNO_USART` を VCP の IRQ 番号+16 に
- [ ] `target_serial.c` — `siopcb_table` の `USARTx_IRQn`、
      `target_fput_log`/ポーリング出力の USART インスタンス（**3箇所セットで揃える**）
- [ ] `target_kernel.py` — 通常は無変更（ベクタテーブルの `aligned` 計算は
      `TMAX_INTNO` から自動。**削らないこと**）
- [ ] `target_timer.{c,h,cfg}` — TIM2/TIM5 構成なら無変更

## チップ層（別系列チップの場合のみ）

- [ ] `asp3/arch/arm_m_gcc/<新chip>/` を `stm32h5xx_stm32cube` からコピー
- [ ] `arch.cmake` — `TOPPERS_CORTEX_M*`・`__TARGET_ARCH_THUMB`・FPU define
- [ ] **`TOPPERS_ENABLE_TRUSTZONE` を安易に足さない**
      （TZEN 無効チップでは EXC_RETURN が変わり仕様上不正になる。
      [../reference/vector-vtor-pitfalls.md](../reference/vector-vtor-pitfalls.md) §2）

## ビルド・実機検証（この順で）

- [ ] `cmake --preset Debug && cmake --build build/Debug` が通る
- [ ] バイナリ検査（書込み前にやると早い）:
  - `grep "_kernel_vector_table$" build/Debug/*.map` → アドレスが
    「エントリ数×4 以上の2のべき乗」境界か（現行 H5 ターゲットは 148 エントリ＝1024）
  - `objdump -d *.elf | grep -A1 exc_return_const` → TZEN 無効なら `0xffffffbc`
- [ ] 書込み → シリアルでバナー・`Sample program starts`・`r` でタスク切替
- [ ] **test_porting 6/6**（SKILL.md §4 の `-D` 差し替えでビルド・書込み）
- [ ] `asp3/asp3_core/docs/dev/stm32-integration.md` に検証結果を記録
