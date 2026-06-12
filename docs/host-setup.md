# 実機検証ホストPCの初期セットアップ（一度きり）

新しい Linux PC を NUCLEO ボードの実機検証ホストにする際の準備手順。
2026-06-12 に deskmini（Ubuntu / ST-LINK V3 内蔵 NUCLEO-H533RE）で実際に
踏んだ問題と解決をそのまま記録したもの。ツールの**日常操作**は
`.claude/skills/porting-asp3-to-stm32/reference/flash-debug-tools.md` を参照。

## 1. 必要ツールと所在

| ツール | 入手 | 備考 |
|---|---|---|
| arm-none-eabi-gcc / cmake / ninja | ディストリのパッケージ | 検証済み: gcc 13.2.1 |
| STM32CubeMX | ST サイトから（zip 展開） | 検証済み: 6.17.0。例: `~/STM32CubeMX/STM32CubeMX` |
| STM32_Programmer_CLI | VS Code の STM32 拡張導入で bundles に入る（または CubeCLT/CubeProgrammer 単体） | **PATH に入らない**。実体例: `~/.local/share/stm32cube/bundles/programmer/<ver>/bin/STM32_Programmer_CLI` |
| OpenOCD | ディストリのパッケージ | `stm32h5x.cfg` 同梱は不要（スキルの最小 cfg で動く） |
| gdb-multiarch | ディストリのパッケージ | arm-none-eabi-gdb の代替 |

## 2. ST-LINK の USB 権限（udev）— 最初に必ず

素の状態では `/dev/bus/usb/...` が `root:root rw-r--r--` のため、一般ユーザの
`STM32_Programmer_CLI -l` が `libusb ... errno=13`（write access 必要）で失敗する。

`/etc/udev/rules.d/99-stlink.rules` を作成（deskmini で動作確認済みの内容）:

```
# ST-Link V1
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3744", MODE="0666"
# ST-Link V2
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3748", MODE="0666"
# ST-Link V2-1
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374b", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3752", MODE="0666"
# ST-Link V3
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374e", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374f", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3753", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3754", MODE="0666"
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
# その後 USB を挿し直し
```

> 参考: 同等のルールは stlink-gdbserver bundle 同梱
> （`~/.local/share/stm32cube/bundles/stlink-gdbserver/<ver>/bin/49-stlinkv*.rules`）
> にもあるが、自動ではインストールされない。

## 3. シリアル（ST-LINK VCP）の権限

`/dev/ttyACM0` は `root:dialout`。ユーザを dialout グループへ（要再ログイン）:

```bash
sudo usermod -aG dialout $USER
```

## 4. ST-LINK ファームウェア更新

古い FW（例: V3J13M4）だと **ST-LINK_gdbserver が「firmware upgrade required」で
起動拒否**する（STM32_Programmer_CLI は古い FW でも動くため気づきにくい）。
STM32CubeProgrammer GUI（Firmware upgrade）で更新する。V3J17M10 で全ツール動作確認済み。
なお本リポジトリのデバッグ正攻法は OpenOCD であり（スキル参照）、
gdbserver を使わないなら更新は必須ではないが、揃えておくのが無難。

## 5. STM32CubeMX の初回起動（新マシン固有）

新マシンの CubeMX は初回起動時に **User Preferences（データ収集同意）等の
モーダルダイアログ**が出る。これがヘッドレス実行を確実にブロックするため、
**初回は必ず GUI で起動して**同意 → `.ioc` を開いて GENERATE CODE まで一度通す。
FW パック（FW_H5 V1.6.0 等）はこのとき自動 DL される（`~/STM32Cube/Repository/`）。

SSH 越しに作業していてローカルのデスクトップセッションがある場合、
そのデスクトップ上に GUI を出せる:

```bash
DISPLAY=:0 XAUTHORITY=$(ls /run/user/$(id -u)/.mutter-Xwaylandauth.*) \
  ~/STM32CubeMX/STM32CubeMX &
# 以降のダイアログ操作は実席の人に依頼する
```

（X クッキーは GNOME/Wayland では `.mutter-Xwaylandauth.*`。X11 セッションなら
`~/.Xauthority`。）

## 6. 動作確認（3点で完了判定）

```bash
# ① ST-LINK が見える（Board Name にボード名が出る）
STM32_Programmer_CLI -l

# ② シリアルが読める
stty -F /dev/ttyACM0 115200 cs8 -cstopb -parenb -echo -icrnl raw && timeout 3 cat /dev/ttyACM0

# ③ ビルド→書込み→バナー（CubeMX 生成済み前提）
cd nucleo_h533re && cmake --preset Debug && cmake --build build/Debug
STM32_Programmer_CLI -c port=SWD reset=HWrst -w $PWD/build/Debug/H533.elf -v -rst
```

## 既知の紛らわしいエラー（無害）

- `STM32_Programmer_CLI -l` の `Error: Could not connect to the J-Link/Flasher,
  Library not found !` — J-Link 探索の失敗で **ST-LINK 利用には無関係**。
- `No STM32 device in DFU mode connected` — DFU 探索の表示で同じく無関係。
