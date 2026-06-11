# ベクタテーブル・VTOR・TrustZone の落とし穴（ARMv8-M / STM32H5）

H533RE 実機ブリングアップで特定した root cause 群。他の STM32 系列・
外部 SDK 統合（リンカスクリプトを SDK が握る構成）全般に適用できる知見。

## 1. ベクタテーブルの整列要件（最重要・実害確認済み）

**要件**: ARMv8-M/ARMv7-M の VTOR は、ベクタテーブルが
**「エントリ数×4 以上の2のべき乗」境界**に置かれていることを要求する。
エントリ数はカーネル cfg の `TMAX_INTNO`（ターゲット依存部）で決まる。
現行の H533/H563 ターゲットはともに 148 エントリ（592B）→ **1024B 整列**。
257 エントリ以上のチップでは 2048B になる（テンプレートが自動計算）。

**何が起きるか**: VTOR 書込み時に下位ビットが**無言で切り捨てられ**、
実効ベースが手前にずれる。全ベクタが「ずれた位置」からフェッチされ、
スロット内容は近傍の rodata/コードの切れ端になる。

**なぜこの構成で踏むか**: CubeMX 生成のリンカスクリプトに ASP3 の `.vector`
セクションの配置規則が無く、**orphan section として 4byte 整列**で置かれる。
一方 `core_initialize()` は `VTOR = _kernel_vector_table` を設定する。

**対策（実装済み）**: `target_kernel.py`（cfg テンプレート）がテーブルに
`__attribute__((section(".vector"), aligned(N)))` を生成する。
N は `TMAX_INTNO` から動的計算。**リンカスクリプトには手を入れない**
（CubeMX 再生成で消えるため）。

**観測された症状の例**（テーブルが 0x...D710 → 実効 0x...D700、4スロットずれ）:
- SysTick(15) のベクタが table[11]=`svc_handler` に → アイドル中の最初の tick で
  `r4`（ゴミ=0）+0x20 を読み精密 BusFault（CFSR=0x8200, BFAR=0x20）
- IRQ（16以上）はずれ先もほぼ `core_int_entry` で**正常動作してしまう**
  （バナーが出る・UART も動く）ため発見が遅れる
- 「被フォルト文脈の IPSR と PC の所属関数の矛盾」が決定的証拠になる

## 2. TOPPERS_ENABLE_TRUSTZONE と EXC_RETURN

arm_m 共通部は `TOPPERS_ENABLE_TRUSTZONE` の有無で例外復帰値を切り替える
（`arm_m.h`）:

| 構成 | HW が生成する EXC_RETURN（thread/PSP） | 定義 |
|---|---|---|
| Secure ブート（例: RP2350/pico2_arm） | `0xFFFFFFFD`（ES/S=1） | 定義する |
| TZEN 無効の STM32H5（出荷時 0xC3=disabled） | `0xFFFFFFBC` | **定義しない** |

pico2_arm の `arch.cmake` を流用すると定義が紛れ込む。TZEN 無効チップで
`0xFFFFFFFD` を使うのは RES0 ビットに 1 を立てる**仕様上不正な値**
（H533 実機では偶然動いたが保証はない）。

確認: `STM32_Programmer_CLI -c port=SWD -ob displ | grep -i tzen` と
`objdump -d *.elf | grep -A1 exc_return_const`。

## 3. target_fput_log は SIO ポーリング出力で実装する

porting 仕様の低レベルログ出力。`putc(stdout)` ＋空 `_write_r(){}` だと
**一切出力されない**（CubeMX の syscalls.c は `__io_putchar` 未実装）。

正: USART レジスタ直接ポーリング（HAL・stdio 非依存。カーネル起動前・
CPU ロック中・例外文脈でも動く）:

```c
static void h533_uart_fput(char c)
{
    while ((USART2->ISR & USART_ISR_TXE) == 0U) { }
    USART2->TDR = (uint8_t)c;
}
void target_fput_log(char c)
{
    if ((USART2->CR1 & USART_CR1_UE) == 0U) { return; }  /* 初期化前は捨てる */
    if (c == '\n') { h533_uart_fput('\r'); }
    h533_uart_fput(c);
}
```

検証は gdb から `call target_fput_log('X')`（halt 中でもシリアルに出る）。

## 4. ツールチェーンのグローバル --gc-sections

CubeMX の `cmake/gcc-arm-none-eabi.cmake` は `CMAKE_EXE_LINKER_FLAGS` に
`-Wl,--gc-sections` をグローバル付与する。cfg1_out（cfg のオフセット抽出用 ELF）
の未参照シンボルが GC され `'TOPPERS_magic_number' is not found` で死ぬ。
→ `target.cmake` の `ASP3_LINK_OPTIONS` に `-Wl,--no-gc-sections`（後勝ち）。
最終 exe は CubeMX 側設定のまま GC 有効で問題ない。

## 5. ICF（同一コード畳み込み）によるデバッグ誤誘導

`main()` 末尾の `while(1)` と `Error_Handler` の `while(1)` 等が同一番地に
畳み込まれ、addr2line/gdb bt が無関係な関数名を表示する。
フォルト後に `sta_ker()` が戻って main 末尾に落ちたケースが
「Error_Handler ← MX_ICACHE_Init で停止」に見えた実例あり。
**シンボル名ではなく PC・CFSR・例外フレームを一次情報にする。**

## 6. SysTick の所有権

CubeMX/HAL は SysTick を HAL_Delay 用に使うが、本構成のカーネルは
TIM2(HRT)+TIM5 を使い（`USE_TIM_AS_HRT`）、SysTick 例外スロットも
カーネルテーブル経由になる。`sta_ker()` 後は HAL_Delay/HAL_IncTick が
進まなくなるのは仕様（カーネル起動後は dly_tsk を使う）。
