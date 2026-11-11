
#!/usr/bin/env bash
set -e

# Chuyển đến thư mục dự án
cd "$(dirname "$0")"

# Lấy đường dẫn FFmpeg và FFprobe
FFMPEG_PATH=$(node -p "require('@ffmpeg-installer/ffmpeg').path")
FFPROBE_PATH=$(node -p "require('@ffprobe-installer/ffprobe').path")

export PATH="$(dirname "$FFMPEG_PATH"):$(dirname "$FFPROBE_PATH"):$PATH"

# Cấu hình cache HyperFrames
export HYPERFRAMES_CACHE_DIR="$PWD/.cache"

# Tìm trình duyệt trên Ubuntu nếu chưa cấu hình
if [ -z "${HYPERFRAMES_BROWSER_PATH:-}" ]; then
    for browser in google-chrome chromium chromium-browser; do
        if command -v "$browser" >/dev/null 2>&1; then
            export HYPERFRAMES_BROWSER_PATH="$(command -v "$browser")"
            break
        fi
    done
fi

# Render video
./node_modules/.bin/hyperframes render \
    --output mario-animation.mp4 \
    --fps 30
