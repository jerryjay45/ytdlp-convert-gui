# ytdlp_convert

A friendly wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp): a bash CLI with presets for the common jobs, plus a PyQt6 GUI that drives it. Available as a standalone AppImage or single-file binary, so you don't need Python or PyQt6 to run the GUI.

Modelled on [resolve_convert](https://github.com/jerryjay45/resolve_convert), and it includes a `resolve` preset that transcodes downloads to DaVinci Resolve-friendly formats (DNxHR + PCM) on Linux.

## Features

- **Presets** for best quality, MP4, resolution caps (2160 to 480), audio-only (mp3, m4a, opus, flac, wav) and DaVinci Resolve
- **Common yt-dlp options** as simple flags: subtitles, embedded thumbnail and metadata, SponsorBlock, rate limit, browser cookies, concurrent fragments, download archive, batch files
- **Escape hatch:** pass any other yt-dlp argument straight through with `-x`
- **Dry-run mode** prints the exact yt-dlp command without running it
- **GUI** with URL box, option checkboxes, live colored log and a stop button
- **Packaged** as an AppImage and a single-file binary

## Requirements

| Needed | For | Install |
|---|---|---|
| `yt-dlp` | everything | `sudo pacman -S yt-dlp` or `pipx install yt-dlp` |
| `ffmpeg` | merging, audio extraction, embedding, `resolve` preset | `sudo pacman -S ffmpeg` or `sudo apt install ffmpeg` |
| `libxcb-cursor0` / `xcb-util-cursor` | GUI on bare X11 setups only | `sudo apt install libxcb-cursor0` or `sudo pacman -S xcb-util-cursor` |

yt-dlp is deliberately not bundled in the AppImage or binary. It needs frequent updates when sites change, so keep your system copy current (`yt-dlp -U` or `pipx upgrade yt-dlp`).

## Install and run

### AppImage (recommended)

```bash
chmod +x ytdlp-convert-x86_64.AppImage
./ytdlp-convert-x86_64.AppImage
```

If your system has no FUSE, run it with `APPIMAGE_EXTRACT_AND_RUN=1 ./ytdlp-convert-x86_64.AppImage`. Tools like AppImageLauncher can add it to your app menu.

### Single-file binary

```bash
chmod +x ytdlp-convert
./ytdlp-convert
```

Same app, but it unpacks itself on each launch, so it starts a few seconds slower than the AppImage.

### From source

```bash
pip install PyQt6
chmod +x ytdlp_convert.sh
python3 ytdlp_convert_gui.py      # GUI (keep it next to ytdlp_convert.sh)
./ytdlp_convert.sh -h             # CLI only, no Python needed
```

> The prebuilt binaries are built on Ubuntu 24.04 and need a glibc at least that new. For older distros, rebuild on the oldest system you want to support (see [Building](#building)).

## CLI usage

```bash
./ytdlp_convert.sh [OPTIONS] URL [URL...]
```

```bash
./ytdlp_convert.sh URL                          # best quality, MKV
./ytdlp_convert.sh -p 1080 -s -m -t URL         # 1080p MP4 + subs, metadata, thumbnail
./ytdlp_convert.sh -p mp3 -P -A done.txt URL    # playlist to MP3, skip already-downloaded
./ytdlp_convert.sh -a urls.txt -p 720 -r 2M     # batch file, 720p, limit to 2 MB/s
./ytdlp_convert.sh -p resolve -Q hqx URL        # DNxHR HQX + PCM audio for Resolve
./ytdlp_convert.sh -n -p 720 URL                # dry-run: print the command only
```

### Options

| Flag | Description | Default |
|---|---|---|
| `-o DIR` | Output directory | `./yt_downloads` |
| `-p PRESET` | Download preset (see below) | `best` |
| `-Q QUALITY` | DNxHR profile for `resolve`: `lb`, `sq`, `hq`, `hqx`, `444` | `hq` |
| `-f FORMAT` | Custom yt-dlp format string (overrides the preset's format) | |
| `-a FILE` | Batch file, one URL per line | |
| `-P` | Allow playlists | single video only |
| `-s` | Download and embed subtitles | off |
| `-l LANGS` | Subtitle languages, comma-separated | `en` |
| `-t` | Embed thumbnail | off |
| `-m` | Embed metadata and chapters | off |
| `-k` | SponsorBlock: remove sponsor segments | off |
| `-r RATE` | Rate limit, e.g. `2M`, `500K` | none |
| `-b BROWSER` | Use cookies from a browser (`firefox`, `chrome`, `brave`, ...) | none |
| `-N N` | Concurrent fragment downloads | `1` |
| `-A FILE` | Download archive, skips videos already downloaded | none |
| `-x "ARGS"` | Extra raw yt-dlp arguments, e.g. `-x "--proxy socks5://..."` | |
| `-n` | Dry-run | off |
| `-h` | Help | |

### Presets

| Preset | Result |
|---|---|
| `best` | Best video + audio, MKV container |
| `mp4` | Best MP4-compatible video + audio |
| `2160` `1440` `1080` `720` `480` | Capped at that height, MP4 |
| `mp3` `m4a` `opus` `flac` `wav` | Audio only |
| `resolve` | Downloads best quality, then transcodes to DNxHR `.mov` with 24-bit 48 kHz PCM audio in `<output>/resolve_ready/` |

Notes:
- Files are named `Title [id].ext`. With `-P`, playlists go into a subfolder named after the playlist, with an index prefix.
- The `resolve` preset keeps the original download and skips any file that has already been converted.

## GUI

Launch the AppImage, the binary, or `python3 ytdlp_convert_gui.py`. Paste one or more URLs, pick a preset, tick the options you want, and press **Start Download**. The GUI builds the same command as the CLI and streams its output into the log. Use **Dry-run** to preview the command first.

Multiple URLs are passed to the script through a temporary batch file, which is deleted when the run finishes.

## Building

```bash
./build.sh
```

This installs PyInstaller and PyQt6 if needed, then writes `out/ytdlp-convert-bin` (single-file binary) and `out/ytdlp-convert-x86_64.AppImage`. It downloads `appimagetool` on first run. Build on the oldest distro you want to support, since the result links against the build machine's glibc.

The built app has a hidden `--selftest` flag that checks the bundled script can be found and exits, which is handy for testing a build on a machine without a display:

```bash
QT_QPA_PLATFORM=offscreen ./ytdlp-convert --selftest
```

## Project layout

```
ytdlp_convert.sh        CLI wrapper (all the logic lives here)
ytdlp_convert_gui.py    PyQt6 front-end that calls the script
ytdlp-convert.png       App icon
build.sh                Builds the binary and AppImage
.gitignore
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `yt-dlp not found` | Install yt-dlp (see Requirements) |
| Merging or audio extraction fails | Install ffmpeg |
| GUI won't start: "could not load the Qt platform plugin xcb" | Install `libxcb-cursor0` / `xcb-util-cursor` |
| AppImage won't run | `chmod +x` it, or use `APPIMAGE_EXTRACT_AND_RUN=1` if FUSE is missing |
| Downloads fail with HTTP errors or "sign in" prompts | Update yt-dlp, or try `-b firefox` to use your browser's cookies |
| Binary fails with a glibc error | Rebuild on an older distro with `./build.sh` |

## Credits

Structure and the Resolve transcoding settings follow [resolve_convert](https://github.com/jerryjay45/resolve_convert). Downloading is done entirely by [yt-dlp](https://github.com/yt-dlp/yt-dlp); this project is only a wrapper. Please respect the terms of service of the sites you download from and the rights of content owners.
