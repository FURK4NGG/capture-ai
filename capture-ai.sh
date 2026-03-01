#!/bin/bash
source "$HOME/.config/capture-ai/env.sh"

set -e

BASE="$HOME/.cache/capture-ai"
IMG_DIR="$BASE/images"
CHAT_DIR="$BASE/chats"

mkdir -p "$IMG_DIR"
mkdir -p "$CHAT_DIR"

MODE="$1"

case "$MODE" in

  image)
    GEOM=$(slurp) || exit 0
    IMG="$IMG_DIR/capture_$(date +%s).png"

    grim -g "$GEOM" "$IMG"

    # 🔥 SADECE IMAGE GÖNDER
    python "$HOME/capture-ai/ui.py" "$IMG"
    ;;

  text)
    python "$HOME/capture-ai/ui.py"
    ;;

  *)
    echo "Usage:"
    echo "  capture-ai.sh image"
    echo "  capture-ai.sh text"
    ;;
esac

