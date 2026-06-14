# CLAUDE.md — asp3_stm32cube

TOPPERS/ASP3 Core を STM32Cube HAL（STM32CubeMX 生成プロジェクト）と協調動作させる
**SDK統合リポジトリ**。純カーネル（`asp3_core`）を submodule 参照し、STM32 固有部だけを持つ。

> 設計・経緯の正本は submodule 側 `asp3/asp3_core/docs/dev/stm32-integration.md`。
> カーネル本体の規約は `asp3/asp3_core/AGENTS.md`。

---

## 0. リポジトリ構成

```
asp3_stm32cube/
├── asp3/
│   ├── asp3_stm32cube.cmake         ← 協調ヘルパ（ASP3_TARGET_DIR 等の解決）
│   ├── asp3_core/                   ← submodule（純カーネル＋全アーキ/チップ依存部）※public
│   └── target/                      ← STM32 ターゲット依存部（stm32h533_nucleo・stm32h563_nucleo）
├── nucleo_h563zi/sample1/           ← CubeMX プロジェクト（H563ZI.ioc が正本）
├── nucleo_h533re/sample1/           ← CubeMX プロジェクト（H533.ioc が正本）
├── docs/                            ← host-setup / verification / TODO
└── .claude/skills/porting-asp3-to-stm32/  ← 移植ガイドskill
```

- ツールチェーンは **arm-none-eabi gcc**、構成生成は **STM32CubeMX**（`.ioc` が正本）。
- **重要**：`Drivers/`・`cmake/`・`*.ld`・`CMakePresets.json` は CubeMX 生成物
  （`.gitignore` 対象）。clone 直後はビルド不可で、**最初に CubeMX で GENERATE CODE** が必要。

## 1. ⚠️ 禁則（作業前に必読）

1. **`asp3/asp3_core/`（submodule）配下を直接編集しない**。カーネル本体は上流 ASP3 追従領域。
   変更が必要なら asp3_core リポジトリ側で行い、その `AGENTS.md` の規約（`kernel/`・`include/`・
   `library/` 編集禁止、変更は `target/`・`syssvc/`・新規ファイルに限定）に従う。
   本リポジトリの作業は **STM32 側ファイル（`asp3/target/`・`asp3/asp3_stm32cube.cmake`・各ボード）** に閉じる。
2. **カーネル内で動的メモリ確保を使わない**（`malloc`/`new` 等禁止。静的生成のみ）。

## 2. 取得・ビルド・実機確認

```bash
git clone --recurse-submodules https://github.com/exshonda/asp3_stm32cube.git
# 既存clone: git submodule update --init --recursive
```

- **最初に CubeMX で各ボードの `.ioc` から GENERATE CODE**（生成物復元）。手順は
  README.md・`docs/host-setup.md`（CubeMX の headless 生成手順含む）を参照。
- GUI 生成依存のため **CI ビルドは行わない**（経緯は stm32-integration.md）。
- 実機検証は **NUCLEO-H563ZI／H533RE**。`test_porting` 6/6・testexec で確認済み。
  シリアル `TOPPERS/ASP3 Kernel …` → `task1 is running` の周期出力で基本動作を確認。

## 検証の鉄則

- コードを変更したら **必ずビルドを通してから報告**。「動くはず」で報告しない。
- 実機確認はシリアル出力を根拠とする。
- asp3_core 側に変更が要る場合は別リポジトリで行い、push 権限が無ければ差分を提示して依頼。

## 参考

| 参照 | 用途 |
|---|---|
| `asp3/asp3_core/docs/dev/stm32-integration.md` | STM32 統合の正本（経緯・設計） |
| `asp3/asp3_core/AGENTS.md` | カーネル本体の規約 |
| `docs/host-setup.md` | ホスト環境（CubeMX 等）構築手順 |
| `.claude/skills/porting-asp3-to-stm32/` | STM32 への移植ガイド skill |
