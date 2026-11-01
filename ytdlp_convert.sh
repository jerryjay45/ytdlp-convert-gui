#!/usr/bin/env bash
# =============================================================================
#  ytdlp_convert.sh — Friendly presets + options wrapper around yt-dlp
#
#  Presets cover the common jobs (best quality, resolution caps, audio-only,
#  DaVinci Resolve-friendly DNxHR/PCM output). Anything not covered can be
#  passed straight through to yt-dlp with -x.
#
#  Usage:
#    chmod +x ytdlp_convert.sh
#    ./ytdlp_convert.sh [OPTIONS] URL [URL...]
#
#  Dependencies:  yt-dlp, ffmpeg (needed for merging, audio extraction,
#                 embedding and the "resolve" preset)
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
OUTPUT_DIR="./yt_downloads"
PRESET="best"
CUSTOM_FORMAT=""
BATCH_FILE=""
RATE_LIMIT=""
COOKIES_BROWSER=""
FRAGMENTS=1
SUBS=false
SUB_LANGS="en"
EMBED_THUMB=false
EMBED_META=false
SPONSORBLOCK=false
PLAYLIST=false
ARCHIVE_FILE=""
EXTRA_ARGS=""
DNX_QUALITY="hq"
DRY_RUN=false

# ── Colour helpers ────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi
info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERR]${RESET}   $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── Help ──────────────────────────────────────────────────────────────────────
usage() {
cat <<EOF
${BOLD}ytdlp_convert.sh${RESET} — yt-dlp presets and options in one place

  ${BOLD}USAGE${RESET}
    $0 [OPTIONS] URL [URL...]

  ${BOLD}OPTIONS${RESET}
    -o DIR      Output directory                       (default: ./yt_downloads)
    -p PRESET   Download preset                        (default: best)
                  best    = best video+audio, MKV container
                  mp4     = best MP4-compatible video+audio
                  2160 | 1440 | 1080 | 720 | 480 = cap resolution, MP4
                  mp3 | m4a | opus | flac | wav     = audio only
                  resolve = download best, then transcode to DNxHR .mov
                            + PCM 24-bit WAV audio (DaVinci Resolve, Linux)
    -Q QUALITY  DNxHR profile for 'resolve': lb|sq|hq|hqx|444  (default: hq)
    -f FORMAT   Custom yt-dlp format string (overrides the preset's format)
    -a FILE     Batch file: one URL per line
    -P          Allow playlists (default: single video only)
    -s          Download subtitles and embed them
    -l LANGS    Subtitle languages, comma-separated   (default: en)
    -t          Embed thumbnail
    -m          Embed metadata and chapters
    -k          SponsorBlock: remove sponsor segments
    -r RATE     Rate limit, e.g. 2M or 500K
    -b BROWSER  Use cookies from browser (firefox, chrome, brave, ...)
    -N N        Concurrent fragment downloads          (default: 1)
    -A FILE     Download archive (skip videos already downloaded)
    -x "ARGS"   Extra raw yt-dlp arguments, e.g. -x "--proxy socks5://..."
    -n          Dry-run — print the yt-dlp command, run nothing
    -h          Show this help

  ${BOLD}EXAMPLES${RESET}
    $0 https://youtu.be/VIDEO
    $0 -p 1080 -s -m -t URL
    $0 -p mp3 -P -A done.txt PLAYLIST_URL
    $0 -p resolve -Q hqx -o ~/footage URL
    $0 -a urls.txt -p 720 -r 2M
EOF
exit 0
}

# ── Argument parsing ──────────────────────────────────────────────────────────
while getopts ":o:p:Q:f:a:Pl:stmkr:b:N:A:x:nh" opt; do
  case $opt in
    o) OUTPUT_DIR="$OPTARG" ;;
    p) PRESET="$OPTARG" ;;
    Q) DNX_QUALITY="$OPTARG" ;;
    f) CUSTOM_FORMAT="$OPTARG" ;;
    a) BATCH_FILE="$OPTARG" ;;
    P) PLAYLIST=true ;;
    l) SUB_LANGS="$OPTARG" ;;
    s) SUBS=true ;;
    t) EMBED_THUMB=true ;;
    m) EMBED_META=true ;;
    k) SPONSORBLOCK=true ;;
    r) RATE_LIMIT="$OPTARG" ;;
    b) COOKIES_BROWSER="$OPTARG" ;;
    N) FRAGMENTS="$OPTARG" ;;
    A) ARCHIVE_FILE="$OPTARG" ;;
    x) EXTRA_ARGS="$OPTARG" ;;
    n) DRY_RUN=true ;;
    h) usage ;;
    :) error "Option -$OPTARG requires an argument."; exit 1 ;;
    \?) error "Unknown option: -$OPTARG"; exit 1 ;;
  esac
done
shift $((OPTIND - 1))
URLS=("$@")

[[ ${#URLS[@]} -eq 0 && -z "$BATCH_FILE" ]] && { error "Give at least one URL or -a FILE. Use -h for help."; exit 1; }
[[ -n "$BATCH_FILE" && ! -f "$BATCH_FILE" ]] && { error "Batch file not found: $BATCH_FILE"; exit 1; }

case "$PRESET" in
  best|mp4|2160|1440|1080|720|480|mp3|m4a|opus|flac|wav|resolve) ;;
  *) error "Invalid preset: $PRESET"; exit 1 ;;
esac
case "$DNX_QUALITY" in
  lb|sq|hq|hqx|444) ;;
  *) error "Invalid DNxHR quality: $DNX_QUALITY. Choose lb|sq|hq|hqx|444"; exit 1 ;;
esac
[[ "$FRAGMENTS" =~ ^[0-9]+$ && "$FRAGMENTS" -ge 1 ]] || { error "-N must be a positive integer"; exit 1; }

# ── Dependency check ──────────────────────────────────────────────────────────
check_deps() {
  command -v yt-dlp &>/dev/null || {
    error "yt-dlp not found."
    echo "  Arch:          sudo pacman -S yt-dlp"
    echo "  Debian/Ubuntu: pipx install yt-dlp   (or: sudo apt install yt-dlp)"
    exit 1
  }
  if ! command -v ffmpeg &>/dev/null; then
    warn "ffmpeg not found — merging, audio extraction and embedding will fail."
    [[ "$PRESET" == "resolve" ]] && { error "The 'resolve' preset requires ffmpeg."; exit 1; }
  fi
}

# ── Build the yt-dlp argument list ────────────────────────────────────────────
ARGS=()
PATHS_FILE=""

build_args() {
  local fmt=""

  case "$PRESET" in
    best|resolve) ARGS+=(-f "${CUSTOM_FORMAT:-bv*+ba/b}" --merge-output-format mkv) ;;
    mp4)          ARGS+=(-f "${CUSTOM_FORMAT:-bv*+ba/b}" -S "ext:mp4:m4a" --merge-output-format mp4) ;;
    2160|1440|1080|720|480)
      fmt="bv*[height<=${PRESET}]+ba/b[height<=${PRESET}]"
      ARGS+=(-f "${CUSTOM_FORMAT:-$fmt}" -S "ext:mp4:m4a" --merge-output-format mp4) ;;
    mp3|m4a|opus|flac|wav)
      ARGS+=(-f "${CUSTOM_FORMAT:-ba/b}" -x --audio-format "$PRESET")
      [[ "$PRESET" == "mp3" || "$PRESET" == "m4a" ]] && ARGS+=(--audio-quality 0) ;;
  esac

  # Output template
  if $PLAYLIST; then
    ARGS+=(--yes-playlist -o "${OUTPUT_DIR}/%(playlist_title|)s/%(playlist_index|)s%(playlist_index& - |)s%(title).200B [%(id)s].%(ext)s")
  else
    ARGS+=(--no-playlist -o "${OUTPUT_DIR}/%(title).200B [%(id)s].%(ext)s")
  fi

  if $SUBS; then
    ARGS+=(--write-subs --write-auto-subs --sub-langs "$SUB_LANGS" --embed-subs)
  fi
  $EMBED_THUMB  && ARGS+=(--embed-thumbnail)
  $EMBED_META   && ARGS+=(--embed-metadata --embed-chapters)
  $SPONSORBLOCK && ARGS+=(--sponsorblock-remove sponsor)
  [[ -n "$RATE_LIMIT" ]]      && ARGS+=(--limit-rate "$RATE_LIMIT")
  [[ -n "$COOKIES_BROWSER" ]] && ARGS+=(--cookies-from-browser "$COOKIES_BROWSER")
  [[ "$FRAGMENTS" -gt 1 ]]    && ARGS+=(--concurrent-fragments "$FRAGMENTS")
  [[ -n "$ARCHIVE_FILE" ]]    && ARGS+=(--download-archive "$ARCHIVE_FILE")
  [[ -n "$BATCH_FILE" ]]      && ARGS+=(--batch-file "$BATCH_FILE")

  # Record final file paths so the 'resolve' preset knows what to transcode
  if [[ "$PRESET" == "resolve" ]]; then
    PATHS_FILE="$(mktemp)"
    ARGS+=(--print-to-file "after_move:filepath" "$PATHS_FILE")
  fi

  ARGS+=(--newline --progress)

  if [[ -n "$EXTRA_ARGS" ]]; then
    # shellcheck disable=SC2206  # intentional word-splitting of user-supplied args
    ARGS+=($EXTRA_ARGS)
  fi
  ARGS+=("${URLS[@]}")
}

# ── Resolve step: transcode downloaded files to DNxHR + PCM ───────────────────
dnx_profile() { echo "dnxhr_$1"; }

transcode_for_resolve() {
  local out_dir="${OUTPUT_DIR}/resolve_ready" pix_fmt="yuv422p" profile f out
  profile="$(dnx_profile "$DNX_QUALITY")"
  [[ "$DNX_QUALITY" == "hqx" ]] && pix_fmt="yuv422p12le"
  [[ "$DNX_QUALITY" == "444" ]] && pix_fmt="yuv444p12le"
  mkdir -p "$out_dir"

  [[ -s "$PATHS_FILE" ]] || { warn "No files recorded for transcoding."; return 0; }
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    out="${out_dir}/$(basename "${f%.*}").mov"
    if [[ -f "$out" ]]; then warn "Skipping (exists): $out"; continue; fi
    info "DNxHR  $(basename "$f")  →  ${out#"$OUTPUT_DIR/"}  [$profile]"
    if ffmpeg -hide_banner -loglevel error -stats -i "$f" \
        -c:v dnxhd -profile:v "$profile" -pix_fmt "$pix_fmt" \
        -c:a pcm_s24le -ar 48000 -ac 2 -movflags write_colr -y "$out"; then
      success "Done: ${out#"$OUTPUT_DIR/"}"
    else
      error "Failed: $f"; rm -f "$out"
    fi
  done < "$PATHS_FILE"
}

cleanup() { [[ -n "${PATHS_FILE:-}" && -f "$PATHS_FILE" ]] && rm -f "$PATHS_FILE"; return 0; }
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  header "=== ytdlp_convert.sh ==="
  $DRY_RUN || check_deps
  build_args

  info "Preset : $PRESET"
  info "Output : $(realpath -m "$OUTPUT_DIR")"
  [[ "$PRESET" == "resolve" ]] && info "DNxHR  : $DNX_QUALITY ($(dnx_profile "$DNX_QUALITY"))"
  echo

  if $DRY_RUN; then
    warn "DRY-RUN MODE — nothing will be downloaded"
    printf '  yt-dlp'; printf ' %q' "${ARGS[@]}"; echo
    exit 0
  fi

  mkdir -p "$OUTPUT_DIR"
  local rc=0
  yt-dlp "${ARGS[@]}" || rc=$?

  if [[ "$PRESET" == "resolve" ]]; then
    header "=== Transcoding for DaVinci Resolve ==="
    transcode_for_resolve
  fi

  header "=== Summary ==="
  if [[ $rc -eq 0 ]]; then
    success "Finished. Output: $(realpath -m "$OUTPUT_DIR")"
  else
    error "yt-dlp exited with code $rc"
  fi
  exit $rc
}

main
