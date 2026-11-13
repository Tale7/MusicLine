<p align="center">    
  <img src="MusicLineLogo.png" width="200" alt="MusicLine 图标" />    
</p>

<h1 align="center">    
  MusicLine    
</h1>

<p align="center">    
  适用于 Windows 的轻量级透明歌词悬浮窗    
</p>

<p align="center">    
  <img src="https://img.shields.io/badge/platform-Windows-blue" alt="运行平台 Windows">    
  <img src="https://img.shields.io/badge/python-3.11+-yellow" alt="Python 版本">    
  <img src="https://img.shields.io/badge/license-MIT-green" alt="许可证">    
</p>

<p align="center">    
  <b>语言 / Language：</b> <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>    
</p>

**MusicLine** 是一个极简、开源的桌面歌词显示工具。它会自动识别你正在播放的歌曲（Apple Music 或任意播放器），把带时间轴的歌词渲染成一层透明的悬浮窗，覆盖在其他窗口之上——工作时、玩游戏时、浏览网页时都能跟着唱。

> [!NOTE]  
> **本项目是二次开发分支（fork / 衍生作品），并非原创项目。** 本作基于上游项目 **KaraokeBird**（[joshshiman/karaokebird](https://github.com/joshshiman/karaokebird)）二次开发，上游采用 MIT 许可证。本分支在其基础上新增了多语言界面、自动歌词翻译、重写的多源歌词获取与稳定性修复。上游版权声明逐字保留在 `LICENSE` 中，完整说明见下文「许可与开源说明」。

# 🚀 功能特性

MusicLine 的设计目标是「不打扰」。

🎤 **实时同步**：自动获取 `.lrc` 歌词，在演唱的那一刻高亮对应歌词行。

👻 **零干扰悬浮窗**：窗口对鼠标点击完全穿透。你可以照常点击、输入、操作歌词后面的窗口，就像它不存在一样。

🎧 **隐私优先、免安装**：无需注册账号、无需强制填写 API 密钥、不上传任何遥测数据。通过 Windows 媒体控制兼容 **Spotify**、**YouTube Music**、**Apple Music** 以及浏览器里的播放器。只有你主动开启翻译，才会产生译文相关的数据传输。

🎨 **外观完全可定制**：

- **字体排版**：自定义字体、描边粗细、高亮颜色。
- **布局**：拖动滑块即可把歌词放到屏幕顶部、底部或中间。
- **动画**：可开启柔和的淡入淡出过渡效果。
- **上下文行**：自由选择显示上一句 / 下一句，或只保留当前一句。

🌐 **多语言界面**：English、简体中文、日本語，并可选用自动歌词翻译（见下文）。

⚡ **开箱即用**：无需登录、无需复杂配置，运行即可。只有选择「自定义 AI API」翻译引擎时才需要填写 API 密钥。

# 💻 安装与使用

### 方式一：直接下载 exe（推荐）

到 [Releases 页面](https://github.com/Tale7/MusicLine/releases) 下载 `MusicLine-win64.zip`，解压后运行 `MusicLine.exe`，**无需安装 Python**。首次运行可能弹出 Windows SmartScreen「未知发布者」提示，确认来源可信后选择「仍要运行」即可。

### 方式二：从源码运行

#### 环境要求

- Windows 10 或 11
- Python 3.11 或更高版本

#### 步骤

1. **克隆仓库：**
   ```bash
   git clone https://github.com/Tale7/MusicLine.git
   cd MusicLine
   ```
   上面的克隆地址指向本分支；原始上游项目见 [joshshiman/karaokebird](https://github.com/joshshiman/karaokebird)。
2. **安装依赖：**
   ```bash
   pip install -r requirements.txt
   ```
3. **启动程序：**
   ```bash
   python main.py
   ```
4. **播放音乐:** 在 Apple Music 或任意播放器里开始播放，歌词会自动出现。

# ⚙️ 设置

在系统托盘（时钟附近）找到 **MusicLine 图标**（蓝底白色音符）。

- **右键**图标，选择 **设置...** 打开配置面板。
- **同步偏移（秒）**：如果歌词整体偏早或偏晚，用设置里的滑块微调时间。

# 🛠️ 工作原理

传统歌词软件需要一个独立窗口，MusicLine 则通过 WinSDK「监听」系统的媒体总线，再从多个在线来源获取带时间轴的 LRC 歌词，最后用 PyQt6 的高性能透明图层渲染出来。

- **[PyQt6](https://pypi.org/project/PyQt6/)**：提供稳定可靠的透明 GUI 与悬浮窗能力。
- **[winsdk](https://pypi.org/project/winsdk/)**：直接对接 Windows 媒体控制，读取歌曲元数据和播放进度。
- **LRCLIB / QQ 音乐 / 网易云音乐**：由 `lyrics_sources.py` 按顺序尝试的 LRC 歌词源。

# 🤝 参与贡献

MusicLine 是开源项目，欢迎贡献代码或翻译！

1. Fork 本仓库。
2. 创建功能分支（`git checkout -b feature/AmazingFeature`）。
3. 提交改动（`git commit -m 'Add some AmazingFeature'`）。
4. 推送分支（`git push origin feature/AmazingFeature`）。
5. 发起 Pull Request。

# 📝 许可与开源说明

本仓库是 [joshshiman/karaokebird](https://github.com/joshshiman/karaokebird) 的 **Fork / 衍生作品**，上游采用 MIT 许可证。

## ⚠️ 第三方服务与内容

- 歌词在运行时从 **LRCLIB**、**QQ 音乐**、**网易云音乐**获取；翻译使用 **Microsoft Bing**、**Google 翻译**、**MyMemory** 或用户自行配置的 OpenAI 兼容端点。这些都是独立第三方服务（部分接口未公开），随时可能变更或限流，并受其自身条款约束。本项目与它们均无关联。
- 歌词是受版权保护的作品，仅**缓存在用户本机**用于播放，不提交到仓库、也不随发布包分发。绝不要把 `lyrics_cache/` 加入 git。
- 查歌词会把歌名和艺术家发给所选来源；翻译会把当前歌曲的歌词行发给所选引擎。两者都是上文说明的可选行为。
- 上方图标（蓝底白色音符）由本分支提供，并非上游的小鸟 logo；上游代码的版权与许可声明仍逐字保留在 `LICENSE` 中。

# 🌐 多语言界面

本分支加入了一套轻量 i18n 层，界面内置 **English**、**简体中文**、**日本語**。

- 打开 **设置 → 系统 → 界面语言：** 选择语言，保持 **自动（跟随系统语言）** 则跟随 Windows 显示语言；保存不同语言后程序会自动重启生效。
- 语言包放在 `langs/*.json`，由程序自动发现。想新增语言，把 `langs/en_US.json` 复制为 `langs/<代码>.json`，填写 `_meta.name` 并翻译 `strings` 里的值，重启后下拉框里就会出现——无需改代码。
- 英文原文即查找键，缺译会安全回退到英文。请保留 `{title}` 等占位符和 `<small>` 之类的 HTML 标签。
- Qt 自带对话框（颜色选择器、标准按钮）通过打包的 `qtbase_<语言>.qm` 本地化。
- 包含语言选择在内的 `settings.json` 保存在 exe 同级目录。

用 `build_exe.bat` 可构建独立 exe。推荐 Python 3.11，因为 `winsdk` 提供了该版本的预编译 wheel；`requirements.txt` 因此固定为 `winsdk==1.0.0b9`。

# 🈯 自动歌词翻译

本分支可以在**当前高亮歌词行的正下方**显示译文。打开 **设置 → 翻译** 进行配置。

- **启用自动翻译**：功能开关，默认关闭。
- **源语言： / 目标语言：**：内置 24 种语言；源语言默认 **自动检测**，目标语言默认 **简体中文**。
- **译文字号： / 译文颜色：**：译文行可独立于原歌词单独设置样式。
- **翻译引擎：** 选择后端：
  - `内置免费（Bing → Google → MyMemory）`——默认项，免费、无需密钥、无需账号。优先请求 **Microsoft Bing**，端点不可达时依次回退到 **Google 翻译** 和 **MyMemory**。**任何环节都不使用百度翻译。**
  - `Microsoft Bing（免费、免密钥）` / `Google 翻译（免费、免密钥）` / `MyMemory（免费、免密钥）`——强制只用某一个免费引擎。
  - `自定义 AI API`——改用你自己的模型。
- **自定义 AI API（OpenAI 兼容）** 支持任意 `/chat/completions` 端点：OpenAI、DeepSeek、Moonshot、Ollama、LM Studio、one-api 等。填写 **API 地址：**（如 `https://api.openai.com/v1`）、**API 密钥：** 和 **模型：**，然后点 **测试连接**——它会翻译一个示例句子并报告成功或后端错误，且不会保存任何内容。本地端点（localhost / 127.0.0.1）会自动绕过系统代理。
- API 密钥仅保存在 exe 同级的 `settings.json`，且只发送给你自己配置的那个端点。

实现要点：

- `translator.py` 承载全部后端（纯 Python，不依赖 Qt）；`translation_controller.py` 在后台线程中调度，通过 Qt 排队信号把结果送回界面，网络慢也不会卡住悬浮窗。
- 整首歌按 **每批 20 行** 翻译，而不是逐行发请求；结果分块流式返回。内存缓存以 `(engine, source, target, model, text)` 为键，重复播放同一首歌几乎瞬时完成。空行、`...` 前奏标记和纯标点行会跳过。
- 若后端返回行数与预期不符，该批会退化为逐行重试；AI 回复行数不对时直接丢弃，避免译文与歌词错位。
- 唯一新增的运行时依赖是 `requests`。

隐私提示：开启任意翻译引擎，都会把**你正在播放歌曲的歌词行**发送给该引擎。关闭此功能即可回到原版除取歌词外不联网的状态。

# 🎵 歌词来源与稳定性

上游原代码把未经处理的 `"<歌名> <艺术家>"` 字符串直接交给 `syncedlyrics`。这很脆弱：Apple Music 这类播放器会把额外信息塞进艺术家字段（`Taylor Swift — Red`、`DECO*27 — Ghost`），而且在窗口最小化时还会变化。原始字符串同时被当作曲目身份，于是这种抖动会被误判为「切歌」，清掉屏幕上已有的歌词，再触发一次可能失败的联网搜索。

本分支用 `lyrics_sources.py` 替换了这套逻辑：

- **稳定的曲目身份。** 先归一化元数据：去掉 `(Taylor's Version)` / `(Explicit)` / `(Remastered 2011)` 等版本标记、`- Single`、`feat. ...`、Apple Music 的 `艺术家 — 专辑` 后缀，并统一全角/半角连字符。同一首歌的元数据抖动会被直接忽略——不重新加载、不闪屏。
- **查找失败绝不擦掉已显示的歌词。** 只有真正切歌才清空悬浮窗；所有来源都失败时，屏幕上的歌词保持不动。只有确实是一首新歌且还没有歌词时，才显示「未找到同步歌词」。
- **四个独立来源**，默认按顺序尝试：
  1. **LRCLIB** 精确匹配（`/api/get?track_name=...&artist_name=...`）
  2. **QQ 音乐**（搜索 → `songmid` → LRC）
  3. **LRCLIB** 模糊搜索——对结果排序后，取第一条**确实带有** `syncedLyrics` 的记录（上游只检查了第一条结果）
  4. **网易云音乐**（搜索 → 歌曲 id → LRC）  
     只接受含真实时间戳的 LRC，纯文本歌词不会造成莫名其妙的「未找到」状态。不使用百度。已移除连不上的 Musixmatch / Genius / Deezer / Megalobiz 来源，顺带省掉了每次查找约 2 秒的超时等待。
- **两级缓存。** 结果同时缓存在内存和 exe 同级 `lyrics_cache/` 下的 JSON 文件里。重听同一首歌、或遇到元数据抖动时都能瞬时命中，离线也能用。失败结果会被抑制 30 秒，避免反复冲击各个来源。
- **诊断日志。** exe 同级的 `lyrics.log` 记录每次查找、命中的来源与耗时（上限 256 KB，自动轮转），某首歌异常时很方便排查。

打开 **设置 → 系统 → 歌词来源：**，可在 `自动（LRCLIB → QQ音乐 → 网易云）`、`仅 LRCLIB`、`仅 QQ 音乐`、`仅网易云音乐` 之间切换，并用 **清空歌词缓存** 清理缓存。

请注意：获取歌词会把**歌名和艺术家**发给所选来源；开启翻译还会把歌词文本发给你选择的翻译引擎。
