# STM32CubeMX コード生成の運用

`.ioc` が正本、生成物（`Drivers/ cmake/ *.ld CMakePresets.json` ほか）は
.gitignore 対象。clone 直後はビルド不可で、**生成して復元**する必要がある。

## GUI で生成する（確実な方法）

1. STM32CubeMX（動作確認済み: 6.17.0）を起動し `nucleo_*/*.ioc` を開く
2. 旧バージョン .ioc なら移行ダイアログ → **Migrate**（常に現行版に合わせる方針）
3. FW パッケージ（例: FW_H5 V1.6.0）未導入なら Download 確認 → 許可（自動 DL）
4. **GENERATE CODE** → `Core/ Drivers/ cmake/ *.ld CMakePresets.json` が復元される

`Core/Src/main.c` 等の **USER CODE BEGIN/END 間は再生成でも保持される**
（`sta_ker()` 呼び出し等はそこに置いてある）。

## ヘッドレス生成は基本不可（ハマりどころ）

- `STM32CubeMX -q script` は **X ディスプレイが無いと起動すら失敗**する
  （`java.awt.HeadlessException`。-q でも JFrame を作る）。
- X があっても **モーダルダイアログで停止**する：初回 User Preferences 同意、
  Project Manager Settings、FW 未導入時の Download 確認、.ioc 移行確認。
  `config load` は通るが `project generate` で固まるのが典型。
- 回避策（環境が許す場合のみ）: `xvfb-run` + `xdotool` で仮想ディスプレイ上の
  ダイアログをスクリーンショット確認しながらクリックする自動化の前例あり
  （asp3_core docs/dev/stm32-integration.md 1枚目「CubeMX 生成（headless 自動化）」）。
  xvfb/xdotool が無いマシンでは素直に GUI 操作を依頼する。

## バージョン方針

- CubeMX / HAL / CMSIS は**導入時点の現行版**に合わせる（移植元の旧版に固定しない）。
- 再生成で `.ioc` 自体も書き換わる（バージョン・メタデータ並び）。`.ioc` の
  diff が並び替えだけなら機能変更なし（chore としてコミット）。

## 生成物とリポジトリの境界

| もの | 扱い |
|---|---|
| `*.ioc` | コミット（正本） |
| `Core/`（USER CODE 含む `main.c`・`stm32h5xx_it.c` 等） | コミット |
| `startup_stm32*.s` | コミット（リセットは CubeMX 側が握る設計） |
| `Drivers/`、`cmake/`、`*.ld`、`CMakePresets.json` | .gitignore（再生成で復元） |
| `build/` | .gitignore |
