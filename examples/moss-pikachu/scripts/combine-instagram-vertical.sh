#!/usr/bin/env bash
set -euo pipefail

# 9:16 Instagram vertical — demo on top, voiceover on bottom (1080x1920).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROMO="$ROOT/promo"

WIDTH=1080
HEIGHT=1920
HALF_H=960

DEMO_VIDEO="${DEMO_VIDEO:-$PROMO/picklight-promo.mp4}"
VOICEOVER_MOV="${VOICEOVER_MOV:-$(find "$ROOT" -maxdepth 1 -name 'Movie on 7-6-26*.mov' -print -quit)}"
OUTPUT="${OUTPUT:-$PROMO/picklight-instagram-vertical.mp4}"
MUSIC_VOLUME="${MUSIC_VOLUME:-0.15}"

FFMPEG="${FFMPEG:-$(command -v ffmpeg || true)}"
FFPROBE="${FFPROBE:-$(command -v ffprobe || true)}"

if [[ -z "$FFMPEG" || -z "$FFPROBE" ]]; then
  echo "error: ffmpeg/ffprobe not found (install with: brew install ffmpeg)" >&2
  exit 1
fi

if [[ -z "$VOICEOVER_MOV" || ! -f "$VOICEOVER_MOV" ]]; then
  echo "error: voiceover MOV not found (set VOICEOVER_MOV or add Movie on 7-6-26*.mov to examples/moss-pikachu/)" >&2
  exit 1
fi

if [[ ! -f "$DEMO_VIDEO" ]]; then
  echo "error: demo video not found: $DEMO_VIDEO" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

DURATION="$("$FFPROBE" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VOICEOVER_MOV")"
DEMO_DURATION="$("$FFPROBE" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$DEMO_VIDEO")"
PAD_SECONDS="$(python3 -c "print(max(0.0, float('${DURATION}') - float('${DEMO_DURATION}')))")"

echo "Demo:      $DEMO_VIDEO"
echo "Voiceover: $VOICEOVER_MOV"
echo "Output:    $OUTPUT"
echo "Format:    ${WIDTH}x${HEIGHT} (9:16)"
echo "Duration:  ${DURATION}s (pad demo ${PAD_SECONDS}s)"

FILTER="[0:v]scale=${WIDTH}:${HALF_H}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HALF_H}:(ow-iw)/2:(oh-ih)/2:black,fps=30,tpad=stop_mode=clone:stop_duration=${PAD_SECONDS}[top];[1:v]scale=${WIDTH}:${HALF_H}:force_original_aspect_ratio=increase,crop=${WIDTH}:${HALF_H},fps=30[bottom];[top][bottom]vstack=inputs=2:shortest=0[v];[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=1.0[voice];[0:a]aresample=48000,aformat=channel_layouts=stereo,volume=${MUSIC_VOLUME}[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=0[a]"

"$FFMPEG" -y \
  -i "$DEMO_VIDEO" \
  -i "$VOICEOVER_MOV" \
  -filter_complex "$FILTER" \
  -map "[v]" \
  -map "[a]" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  -t "$DURATION" \
  "$OUTPUT"

echo "Wrote $OUTPUT"
