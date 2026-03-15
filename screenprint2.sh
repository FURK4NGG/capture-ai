#!/usr/bin/env bash
set -euo pipefail

DIR="$HOME/Resimler"
mkdir -p "$DIR"

ARG="${1:-}"

notify_ok() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "Screenshot taken" "$1"
    fi
}

take_fullscreen() {
    local file="$DIR/tam-ekran-$(date +%Y%m%d-%H%M%S).png"
    grim "$file"
    notify_ok "All Screens"
    printf '%s\n' "$file"
}

take_selection_or_click() {
    local geom file
    geom="$(slurp 2>/dev/null || true)"

    # kullanıcı iptal ettiyse sessiz çık
    [ -z "$geom" ] && exit 0

    # küçük seçimleri de direkt seçili alan gibi kaydet
    file="$DIR/secili-alan-$(date +%Y%m%d-%H%M%S).png"
    grim -g "$geom" "$file"
    notify_ok "Selected Area"
    printf '%s\n' "$file"
}

case "$ARG" in
    "")
        take_fullscreen
        ;;
    only-one)
        take_selection_or_click
        ;;
    -h|--help|help|-help)
        echo "Kullanim/Usage:"
        echo "  $0           -> Take screenshot for all screens"
        echo "  $0 only-one  -> Select area and save it"
        ;;
    *)
        echo "Kullanim/Usage:"
        echo "  $0           -> Take screenshot for all screens"
        echo "  $0 only-one  -> Select area and save it"
        exit 1
        ;;
esac
