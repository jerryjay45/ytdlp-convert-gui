#!/usr/bin/env bash
# Rebuilds the single-file binary and AppImage. Run on the oldest distro you want to support
# (binaries link against the build machine's glibc).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
pip install pyinstaller PyQt6 --break-system-packages -q || pip install pyinstaller PyQt6 -q
EXCL=(--exclude-module PyQt6.QtNetwork --exclude-module PyQt6.QtSql --exclude-module PyQt6.QtQml --exclude-module tkinter)
DATA=(--add-data "$PWD/ytdlp_convert.sh:.")
python3 -m PyInstaller --noconfirm --clean --onefile --name ytdlp-convert-bin "${DATA[@]}" "${EXCL[@]}" \
  --distpath out --workpath build/one --specpath build ytdlp_convert_gui.py
python3 -m PyInstaller --noconfirm --clean --onedir --name ytdlp-convert "${DATA[@]}" "${EXCL[@]}" \
  --distpath build/dist --workpath build/dir --specpath build ytdlp_convert_gui.py
rm -rf AppDir && mkdir -p AppDir/usr/lib
cp -r build/dist/ytdlp-convert AppDir/usr/lib/
cp ytdlp-convert.png AppDir/ytdlp-convert.png && cp ytdlp-convert.png AppDir/.DirIcon
printf '[Desktop Entry]\nType=Application\nName=yt-dlp Converter\nComment=Download video or audio with yt-dlp presets\nExec=ytdlp-convert\nIcon=ytdlp-convert\nTerminal=false\nCategories=AudioVideo;Network;\n' > AppDir/ytdlp-convert.desktop
printf '#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/lib/ytdlp-convert/ytdlp-convert" "$@"\n' > AppDir/AppRun
chmod +x AppDir/AppRun
[[ -x appimagetool ]] || { curl -sSL -o appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage; chmod +x appimagetool; }
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 ./appimagetool --no-appstream AppDir out/ytdlp-convert-x86_64.AppImage
echo "Done -> out/"
