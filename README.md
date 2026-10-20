# ytdlp_convert

yt-dlp presets and options wrapped in a bash CLI, plus a PyQt6 GUI. Modelled on resolve_convert.

- `ytdlp_convert.sh`     — CLI (`./ytdlp_convert.sh -h` for all options)
- `ytdlp_convert_gui.py` — GUI front-end (keep it in the same folder as the .sh)

## Requirements
- yt-dlp, ffmpeg
- GUI only: `pip install PyQt6`

## Quick start
    chmod +x ytdlp_convert.sh
    ./ytdlp_convert.sh URL                      # best quality, MKV
    ./ytdlp_convert.sh -p 1080 -s -m -t URL     # 1080p MP4 + subs, metadata, thumbnail
    ./ytdlp_convert.sh -p mp3 -P -A done.txt PLAYLIST_URL
    ./ytdlp_convert.sh -p resolve -Q hqx URL    # DNxHR + PCM WAV audio for DaVinci Resolve
    ./ytdlp_convert.sh -n -p 720 URL            # dry-run: print the yt-dlp command only
    python3 ytdlp_convert_gui.py
