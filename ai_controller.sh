#!/bin/bash
source ~/.config/ai_capture/env.sh

set -e

TMP="$HOME/.cache/ai-capture"
mkdir -p "$TMP"

GEOM=$(slurp) || exit 1
IMG="$TMP/capture_$(date +%s).png"

grim -g "$GEOM" "$IMG"

python ~/ai_capture/ui.py "$IMG"
