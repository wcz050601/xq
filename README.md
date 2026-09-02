# Python 中国象棋（桌面 / Android）

这是一个使用 Python 与 Kivy 编写的中国象棋项目。它支持：

- 完整的中国象棋基本走子规则、将军判定与将帅照面限制
- 本地双人和 WebSocket 双人联网对弈
- Windows、Linux、macOS 桌面端，以及 Android 客户端
- 自由设置局时与步时（设置为 0 表示不限时）
- 开局让子
- 不限次数请求悔棋；只有对方同意后才会执行
- 落子、吃子、将军、非法步和按钮点击音效；音频文件可自行替换

## 快速开始

建议使用 Python 3.11。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

程序启动后直接进入主菜单。选择“本地双人”会弹出本局设置；选择“联机对弈”后可直接在软件内创建或加入对局。

创建联机对局时，软件会自动启动内嵌服务，并在对局页显示局域网 IP、端口和房间号。把这三项发给对方即可，不需要再打开终端。默认创建者执红。第一次作为主机运行时，Windows 防火墙可能会询问是否允许网络访问；局域网联机需要允许专用网络访问。

### 一键公网对局（不同网络）

Windows 桌面端选择“联机对弈”→“一键创建公网对局”即可自动完成内网穿透：

1. 软件启动本地房间服务。
2. 首次使用时，从 Cloudflare 官方 GitHub 发布页下载 `cloudflared` 到应用数据目录并校验 SHA-256（若发布接口提供校验值）。
3. 软件建立免费的临时 Quick Tunnel，并显示 `wss://...trycloudflare.com` 地址。
4. 点击“复制邀请”，把服务器地址和房间号发给对方。
5. 对方在“加入对局”的“主机 IP 或 WSS 地址”中粘贴完整 `wss://` 地址即可，端口保持默认值。

创建方电脑和象棋程序必须保持运行。临时公网地址每次创建都会变化；Quick Tunnel 是 Cloudflare 提供的免费测试服务，不保证在线率。当前仅支持 64 位 Windows 创建一键公网房间，Windows 和 Android 均可加入。

`server.py` 仍保留为可选的独立公网/长期服务器入口，但普通局域网对弈不需要使用它。

## 操作

- 点击己方棋子选中，再点击目标交叉点走棋。
- “请求悔棋”会向对方发起请求；对方可同意或拒绝。
- 每局结束会询问是否保存；主菜单的“历史棋局复盘”可逐步查看已保存棋局。
- 局时、步时、让子、房间号和端口等设置会记住上一次使用值。
- 联机对局顶部的“聊天”可发送文字消息和快捷表情；收到新消息时按钮会显示圆点。
- 让子项使用英文逗号分隔棋子编号，如 `R1,H1`。编号见下表。

| 红方 | 黑方 | 含义 |
|---|---|---|
| R1/R2 | r1/r2 | 左/右车 |
| H1/H2 | h1/h2 | 左/右马 |
| E1/E2 | e1/e2 | 左/右相/象 |
| A1/A2 | a1/a2 | 左/右仕/士 |
| C1/C2 | c1/c2 | 左/右炮 |
| P1..P5 | p1..p5 | 从左到右的兵/卒 |

将/帅不能设置为让子。联网房间采用创建者设置的计时和让子规则。

## 音效

项目已附带五段简短的默认提示音。你可以把自己的短音频文件放到 `assets/sounds/` 覆盖它们：

- `move.wav`：普通落子
- `capture.wav`：吃子
- `check.wav`：将军提示
- `illegal.wav`：非法走子提示
- `click.wav`：界面按钮点击

文件不存在或设备无法播放时程序会静默运行，不影响对局。运行 `python tools/generate_sounds.py` 可重新生成默认音效。

## Android 打包

### GitHub 一键构建（推荐）

仓库已包含 `.github/workflows/android-apk.yml`：

1. 把本地修改推送到 GitHub。
2. 打开仓库的 **Actions** 页面。
3. 选择 **Build Android APK**。
4. 点击 **Run workflow**，再次点击绿色的 **Run workflow**。
5. 构建完成后，打开该次运行，在页面底部 **Artifacts** 下载 `pyxq-android-apk`。

下载的是 ZIP 压缩包，解压后即可得到可安装的 debug APK。第一次云端构建需要下载 Android SDK/NDK，可能耗时较长。

工作流也会在推送形如 `v0.1.0` 的 Git 标签时自动构建。当前 APK 仅构建现代 Android 手机通用的 `arm64-v8a` 架构，以减少构建时间和失败概率。

### 本地构建

本地 Android 构建建议在 Linux 或 WSL2 中进行（Buildozer 不直接支持原生 Windows 构建）：

```bash
pip install buildozer
buildozer android debug
```

生成的 APK 位于 `bin/`。真机联网时必须把客户端服务器地址改为局域网服务器 IP，不能使用 `localhost`。发布版本还应按 Android/Google Play 要求配置签名和 HTTPS/WSS。

## 测试

核心规则及服务端协议测试不依赖 Kivy：

```powershell
python -m unittest discover -s tests -v
```
