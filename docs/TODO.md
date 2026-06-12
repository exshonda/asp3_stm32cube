# 残課題（2026-06-12 整理）

実機ブリングアップ・検証（H533RE/H563ZI とも sample1・test_porting 6/6・
testexec 32 PASS）は完了済み。以下はその後に残る任意・未決事項。
経緯の正本は `asp3/asp3_core/docs/dev/stm32-integration.md`。

## 1. cpuexc1 / cpuexc4 の方針確定（asp3_core 側・ユーザー判断待ち）

- testexec で FAIL する2本。**上流 TOPPERS/ASP3 arm_m 固有の特性**
  （PRIMASK ベースの `SIL_LOC_INT` 中の UsageFault が HardFault に昇格）で、
  mps2(QEMU)・pico2_arm(実機) と同一挙動＝本リポジトリのバグではない。
- 選択肢（案① SIL を BASEPRI ロック化＝上流乖離／案② 意図的除外として明文化
  ＝推奨）は **`asp3_core docs/dev/issue-cpuexc-armm.md`** に整理済み。

## 2. int1 用ソフト割込み源の整備（任意）

- testexec の int1 が BUILD_FAIL（`target_test.h` に `INTNO1/INTPRI/INTATR`
  等のテスト用ソフト割込み源が未定義）。
- mps2_an521 は**予備 NVIC IRQ をソフト割込み源に整備して 21/21 PASS** の
  前例あり（asp3_core `docs/dev/ci.md` 既知事項表）。STM32 でも未使用 IRQ
  （NVIC の `NVIC->STIR` / ISPR 書込みで ras_int 可能なもの）を選んで
  `target_test.h` に定義すれば対応可能。対象：`asp3/target/stm32cubemx/`・
  `asp3/target/stm32h533_nucleo/` 両方。

## 3. feat/stm32-h5 → main のマージ判断

- 検証完了・push 済み（`bb31c69` 時点）。マージ後は本ブランチの削除も検討。

## 4. その他（小粒・記録のみ）

| 項目 | 内容 |
|---|---|
| H563ZI 旧「無出力」症状 | ベクタ整列違反が原因と推定されるが、旧バイナリでの再現確認はしていない（現構成で解消済みのため実害なし） |
| `EXC_RETURN_PREFIX` 再定義 warning | CMSIS `core_cm33.h`（`0xFF000000UL`）と arm_m.h（`0xff000000`）の重複。非致命・FSP(M85) と同様に未対処 |
| CubeMX ヘッドレス生成 | `-q` でも X 必須＋モーダルダイアログで停止のため GUI 運用。xvfb/xdotool 導入マシンでは自動化の前例あり（stm32-integration.md 1枚目） |
| TrustZone（TZEN 有効）構成 | 未スコープ。対応する場合は `arch.cmake` に `TOPPERS_ENABLE_TRUSTZONE` を定義し Secure 構成で再検証（`.claude/skills/.../vector-vtor-pitfalls.md` §2） |
| CI | CubeMX 生成依存のため GitHub Actions ではビルド対象外（当初方針どおり）。生成物のコミット可否 or コンテナ化で再考の余地 |
