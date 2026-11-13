<p align="center">    
  <img src="MusicLineLogo.png" width="200" alt="MusicLine Logo" />    
</p>

<h1 align="center">    
  MusicLine    
</h1>

<p align="center">    
  The lightweight, transparent lyrics overlay for Windows.    
</p>

<p align="center">    
  <img src="https://img.shields.io/badge/platform-Windows-blue" alt="Platform Windows">    
  <img src="https://img.shields.io/badge/python-3.11+-yellow" alt="Python Version">    
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">    
</p>

<p align="center">    
  <b>Language / 语言：</b> <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>    
</p>

**MusicLine** is a minimal, open-source lyrics visualizer that lives on your desktop. It detects what you are playing on Apple Music (or any media player) and displays time-synced lyrics in a beautiful, transparent overlay that sits on top of your windows—letting you sing along while you work, game, or browse.

> [!NOTE]  
> **This is a fork (derivative work), not an original project.** MusicLine is based on the upstream project **KaraokeBird** by [joshshiman/karaokebird](https://github.com/joshshiman/karaokebird), released under the MIT License. This branch builds on it by adding a multi-language UI, automatic lyric translation, a rewritten multi-source lyrics fetcher and stability fixes. The upstream copyright notice is preserved verbatim in `LICENSE`; full details are in the licence section below.

# 🚀 Features

MusicLine is designed to be seamless and unobtrusive.

🎤 **Real-Time Sync:**: Automatically fetches `.lrc` files to display lyrics exactly when they are sung.

👻 **Zero-Interruption Overlay**: The window uses a click-through window and is fully transparent to input. You can click, type, and interact with windows behind the lyrics as if they weren't there.

🎧 **Privacy-First & Portable**: No account creation, no mandatory API keys, and no telemetry. Works with **Spotify**, **YouTube Music**, **Apple Music**, and browser media players via Windows Media Controls. Translation only sends data when you explicitly enable it.

🎨 **Fully Customizable**:

- **Typography**: Custom fonts, stroke weights, and highlight colors.
- **Layout**: Drag a slider to move the lyrics to the top, bottom, or middle of your screen.
- **Animations**: Enable gentle cross-fades for a smoother visual experience.
- **Context Lines**: Choose to see previous/next lines or keep it minimal with just the current line.

🌐 **Multi-language UI**: English, 简体中文 and 日本語, with optional automatic lyric translation (see below).

⚡ **Instant Setup**: No logins and no complex configuration required. Just run and sing. An API key is only needed if you opt into a custom AI translation backend.

# 💻 Installation & Usage

### Option A — Download the ready-to-run exe (recommended)

Grab `MusicLine-win64.zip` from the [Releases page](https://github.com/Tale7/MusicLine/releases), unzip it and run `MusicLine.exe` — no Python installation needed. Windows SmartScreen may warn about an unsigned binary; choose "Run anyway" only if you trust this build.

### Option B — Run from source

#### Prerequisites

- Windows 10 or 11
- Python 3.11 or higher

#### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Tale7/MusicLine.git
   cd MusicLine
   ```
   The clone URL above points to this fork. The original upstream project is [joshshiman/karaokebird](https://github.com/joshshiman/karaokebird).
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the app:**
   ```bash
   python main.py
   ```
4. **Play music:** Start a song on Apple Music or your preferred player. The lyrics will appear automatically.

# ⚙️ Configuration

Look for the **MusicLine icon** (a white musical note on blue) in your system tray (near the clock).

- **Right-click** the icon and select **Settings...** to open the configuration menu.
- **Sync Offset**: If lyrics are appearing too early or too late, adjust the offset slider in settings to fix the timing.

# 🛠️ How it Works

Unlike traditional lyrics apps that require a dedicated window, MusicLine uses the WinSDK to "listen" to your system's media bus. It then looks up time-synced LRC lyrics through several online providers and renders them via a high-performance PyQt6 transparent layer.

- **[PyQt6](https://pypi.org/project/PyQt6/)**: For the robust, transparent GUI and overlay capabilities.
- **[winsdk](https://pypi.org/project/winsdk/)**: To interface directly with Windows Media Controls for metadata and timeline tracking.
- **LRCLIB / QQ Music / NetEase Cloud Music**: Time-synced LRC providers, tried in order by `lyrics_sources.py`.

# 🤝 Contributions

MusicLine is an open-source project, and contributions are welcome!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

# 📝 License & open-sourcing this fork

This repository is a **fork / derivative work** of [joshshiman/karaokebird](https://github.com/joshshiman/karaokebird), released under the MIT License.

## ⚠️ Third-party services & content

- Lyrics are fetched at runtime from **LRCLIB**, **QQ Music** and **NetEase Cloud Music**; translation uses **Microsoft Bing**, **Google Translate**, **MyMemory** or a user-supplied OpenAI-compatible endpoint. These are third-party services (some undocumented), may change or rate-limit at any time, and are subject to their own terms. This project is not affiliated with any of them. **Baidu Translate is deliberately not used.**
- Lyrics are copyrighted works. They are cached **locally on the user's machine** only, and no lyric text is committed here or bundled in releases. Never add `lyrics_cache/` to git.
- Lyrics lookup sends the title/artist to the chosen provider; translation sends the current song's lyric lines to the chosen backend. Both are opt-in behaviours documented above.
- The icon above (a white musical note on blue) is supplied by this fork, not the upstream bird logo; the upstream code copyright and licence notice remain verbatim in `LICENSE`.

## Publishing checklist

- [x] Repository URLs already point to `Tale7` / `v1.0.0`.
- [ ] Optionally add your own copyright line in `LICENSE` **below** the original one — never remove the original.
- [ ] Check `git status` shows no `settings.json`, `lyrics_cache/`, `lyrics.log`, `dist/*.exe` or `.build-venv/`.
- [ ] Attach `dist/MusicLine-win64.zip` (or the bare exe plus the licence notice) to the Release; rebuild the zip after any source change.
- [ ] Keep `README.md` and `README.zh-CN.md` in sync when editing either one.
- [ ] Keep `MusicLineLogo.png` / `MusicLine.ico` and the upstream credit intact.

# 🌐 Multi-language interface

This fork adds a lightweight i18n layer. The UI ships with **English**, **简体中文** and **日本語**.

- Open **Settings → System → Interface Language** to pick a language, or leave it on **Auto** to follow the Windows display language. Saving a different language restarts the app automatically.
- Language packs live in `langs/*.json` and are discovered automatically. To add a language, copy `langs/en_US.json` to `langs/<code>.json`, set `_meta.name`, and translate the values in `strings`. Restart and it shows up in the dropdown — no code changes needed.
- The English source text is the lookup key, so a missing translation safely falls back to English. Keep placeholders such as `{title}` and HTML tags like `<small>` intact.
- Qt's own dialogs (colour picker, standard buttons) are localised through the bundled `qtbase_<lang>.qm` files.
- `settings.json`, including the chosen language, is stored next to the executable.

Build a standalone exe with `build_exe.bat`. Python 3.11 is recommended because `winsdk` ships prebuilt wheels for it; `requirements.txt` pins `winsdk==1.0.0b9` for that reason.

# 🈯 Automatic lyrics translation

This fork can show a translated line **directly underneath the active lyric line**.
Open **Settings → Translation** to configure it.

- **Enable automatic translation** turns the feature on/off. It is off by default.
- **From / To** choose source and target languages (24 built-in; `Auto detect` is the default source, 简体中文 the default target).
- **Translation Size / Translation Color** style the translated line independently from the original lyric.
- **Engine** selects the backend:
  - `Built-in (Bing > Google > MyMemory)` — the default. Free, no API key, no account. It requests **Microsoft Bing** first and falls back to **Google Translate** and then **MyMemory** if an endpoint is unreachable. **Baidu Translate is deliberately not used anywhere.**
  - `Microsoft Bing (free, no key)` / `Google Translate (free, no key)` / `MyMemory (free, no key)` — force one specific free engine.
  - `Custom AI API` — use your own model instead.
- **Custom AI API** accepts any OpenAI-compatible `/chat/completions` endpoint: OpenAI, DeepSeek, Moonshot, Ollama, LM Studio, one-api, etc. Fill in **API Base URL** (e.g. `https://api.openai.com/v1`), **API Key** and **Model**, then press **Test Connection** — it translates a sample sentence and reports success or the backend error without saving anything. Local endpoints (localhost / 127.0.0.1) bypass the system proxy automatically.
- The API key is stored locally in `settings.json` next to the executable and is only sent to the endpoint you configure.

Implementation notes:

- `translator.py` holds all backends (pure Python, no Qt). `translation_controller.py` runs them on a small thread pool and delivers results to the GUI via queued Qt signals, so the overlay never freezes on a slow network.
- A whole song is translated in **batches of 20 lines** rather than one request per line. Results stream in chunk by chunk, and an in-memory cache keyed by `(engine, source, target, model, text)` makes repeated plays instant. Blank lines, `...` intro markers and pure punctuation are skipped.
- If a backend drifts from the expected line count, that chunk is retried line-by-line; an AI reply with the wrong number of lines is rejected rather than showing misaligned text.
- `requests` is the only added runtime dependency.

Privacy: enabling any translation engine sends **the lyric lines of the song you are playing** to that engine. Leave the feature off to keep the original zero-network behaviour (apart from lyrics fetching).

# 🎵 Lyrics sources & stability

The original upstream code handed the raw `"<title> <artist>"` string to `syncedlyrics`. That was fragile: players such as Apple Music put extra text into the artist field (`Taylor Swift — Red`, `DECO*27 — Ghost`) and can change it when their window is minimised. The raw string was used as the track identity, so such a flicker looked like a track change, wiped the lyrics already on screen and triggered a fresh network lookup that could fail.

This fork replaces that with `lyrics_sources.py`:

- **Stable track identity.** Metadata is normalised (edition tags like `(Taylor's Version)` / `(Explicit)` / `(Remastered 2011)`, `- Single`, `feat. ...`, and Apple Music's `Artist — Album` suffix are removed; full/half-width dashes are unified). A metadata flicker for the same song is therefore ignored — no reload, no flicker.
- **A failed lookup never erases visible lyrics.** Only a real track change clears the overlay. If every provider fails, the existing lyrics stay on screen; the "no synced lyrics found" message appears only when a genuinely new track has no lyrics yet.
- **Four independent providers**, tried in order by default:
  1. **LRCLIB** exact match (`/api/get?track_name=...&artist_name=...`)
  2. **QQ Music** (search → `songmid` → LRC)
  3. **LRCLIB** fuzzy search — ranks results and takes the first one that *actually has* `syncedLyrics` (the upstream provider only checked the first result)
  4. **NetEase Cloud Music** (search → song id → LRC)  
     Only LRC containing real timestamps is accepted, so plain-text lyrics can never produce a silent "not found" state. Baidu is not used. The unreachable Musixmatch / Genius / Deezer / Megalobiz sources were dropped, which also removes the ~2s timeout on every lookup.
- **Two-level cache.** Results are cached in memory and as JSON files in `lyrics_cache/` next to the executable. Replaying a song — or a metadata flicker — is instant and works offline. Failures are suppressed for 30 seconds to avoid hammering the providers.
- **Diagnostics.** `lyrics.log` next to the executable records each lookup, the provider that answered and the elapsed time (capped at 256 KB, auto-rotated). Useful if a particular song ever misbehaves.

Open **Settings → System → Lyrics Source** to choose `Auto`, `LRCLIB only`, `QQ Music only` or `NetEase Cloud Music only`, and to clear the cache with **Clear Lyrics Cache**.

Note that fetching lyrics sends the **song title and artist** to the selected provider(s); translating additionally sends the lyric text to the translation engine you chose.
