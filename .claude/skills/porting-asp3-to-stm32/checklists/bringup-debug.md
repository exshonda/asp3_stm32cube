# 実機ブリングアップ デバッグチェックリスト

実機で動かない時の切り分け手順。H533RE ブリングアップ（真因＝ベクタ整列違反）で
確立した方法。解析の実録は `asp3/asp3_core/docs/dev/stm32-integration.md` 2枚目。

## 0. まず疑う順（症状 → 容疑）

| 症状 | 第一容疑 | 確認方法 |
|---|---|---|
| 何も出ない | クロック/BSP/VCP配線、**ベクタ整列** | バイナリ検査（下記 1） |
| バナーは出るがタスクが動かない | **ベクタ整列**（IRQ は動くがシステム例外 11-15 がずれる） | vector_catch（下記 3） |
| `ras_ter` が `E_CTX` を返すループ | それは**二次症状**。最初のフォルトを探す | vector_catch |
| bt が `Error_Handler ← MX_ICACHE_Init` 等を指す | **ICF 畳み込みの誤誘導**の可能性 | PC・CFSR を一次情報に |
| HAL_Delay/HAL_IncTick が動かない | SysTick をカーネルに取られている（仕様） | — |

## 1. バイナリ検査（書込み前・30秒でできる）

```bash
cd nucleo_*/build/Debug
# ベクタテーブルの整列（エントリ数×4 以上の2のべき乗境界にあること）
grep "_kernel_vector_table$" *.map
# EXC_RETURN（TZEN 無効チップなら 0xffffffbc であること）
arm-none-eabi-objdump -d *.elf | grep -A1 "exc_return_const>:"
# ベクタテーブルの中身（slot11=svc_handler, 14=pendsv, 15以降=core_int_entry）
arm-none-eabi-objdump -s -j .vector *.elf | head
```

## 2. ハードウェア状態の確認

```bash
STM32_Programmer_CLI -l                       # プローブ認識
STM32_Programmer_CLI -c port=SWD -ob displ | grep -i tzen   # TZEN（TrustZone）状態
```

TZEN 無効（H5 出荷時 0xC3=disabled）なら `TOPPERS_ENABLE_TRUSTZONE` を
定義してはいけない（[../reference/vector-vtor-pitfalls.md](../reference/vector-vtor-pitfalls.md) §2）。

## 3. フォルト瞬間を捕まえる（winning technique）

OpenOCD（最小 cfg: [../snippets/openocd-h5.cfg](../snippets/openocd-h5.cfg)）＋ gdb-multiarch:

```bash
openocd -f openocd-h5.cfg &          # gdb server :3333（ST-LINK を排他確保する点に注意）
gdb-multiarch -q build/Debug/*.elf \
  -ex "target extended-remote :3333" \
  -ex "monitor cortex_m vector_catch hard_err bus_err mm_err chk_err state_err nocp_err int_err" \
  -ex "monitor reset halt" -ex "continue"
# フォルト発生瞬間に停止する（reset は catch に入れない）
```

停止したら一次情報を集める:

```
info registers            # pc / lr / xpsr（IPSR=下位9bit）/ r4
p/x *(unsigned int*)0xE000ED28    # CFSR（フォルト種別）
p/x *(unsigned int*)0xE000ED38    # BFAR（BusFault アドレス）
p _kernel_p_runtsk
x/8wx $sp                 # 例外フレーム: r0,r1,r2,r3,r12,lr,pc,xpsr
```

## 4. 読み方の鉄則

- **「被フォルト文脈の IPSR」と「PC の所属関数」が矛盾したらベクタテーブル不正を疑う**。
  例: IPSR=15（SysTick）なのに PC が `svc_handler` 内 → VTOR 整列違反で
  ベクタフェッチがずれ、SysTick が table[11]=svc_handler を引いていた。
- IRQ（例外番号16以上）は `core_int_entry` 経由で **ずれていても動いてしまう**
  （内部で IPSR から exc_tbl を引くため）。「シリアルは動くのに死ぬ」はこのパターン。
- バックトレースは ICF（`Error_Handler` と `main` 末尾 `while(1)` の畳み込み等）で
  平気で嘘をつく。**PC・CFSR・BFAR・スタック上の例外フレームを一次情報**にする。
- `cpuexc_handler` は登録した例外（既定 UsageFault=6）にしか入らない。
  BusFault/HardFault は素通りするので「ハンドラに来ない＝例外なし」ではない。
- gdb から `call target_fput_log('X')` で低レベル出力経路を単体テストできる
  （ポーリング実装なら halt 中でも UART に出る）。

## 5. 切り分け実験の作法

- 仮説の修正を入れたら **1 変数ずつ**実機で確認（H533 では「整列」と「TRUSTZONE」を
  分離テストし、致命傷は整列のみと確定できた）。
- 診断用のコード編集（フォルト情報退避等）は作業メモに「要 revert」と明記し、
  解決後に `git checkout --` で戻す。
- OpenOCD 起動中は `STM32_Programmer_CLI` が `DEV_CONNECT_ERR` になる（ST-LINK 排他）。
  書込み前に OpenOCD を止める。gdb セッションを kill で中断すると
  ターゲットが壊れた状態で走る（偽フォルト）ので、リセットしてから再観測する。
