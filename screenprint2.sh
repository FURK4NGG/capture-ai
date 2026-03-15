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

    if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] && command -v grim >/dev/null 2>&1; then
        grim "$file"
    elif command -v scrot >/dev/null 2>&1; then
        scrot "$file"
    else
        echo "No working screenshot tool found" >&2
        exit 1
    fi

    notify_ok "All Screens"
    printf '%s\n' "$file"
}

take_selection() {
    local file="$DIR/secili-alan-$(date +%Y%m%d-%H%M%S).png"

    if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] && command -v grim >/dev/null 2>&1 && command -v slurp >/dev/null 2>&1; then
        local geom
        geom="$(slurp 2>/dev/null || true)"
        [ -z "$geom" ] && exit 0
        grim -g "$geom" "$file"
    elif command -v scrot >/dev/null 2>&1; then
        scrot -s "$file"
    else
        echo "No working area screenshot tool found" >&2
        exit 1
    fi

    notify_ok "Selected Area"
    printf '%s\n' "$file"
}

case "$ARG" in
    "")
        take_fullscreen
        ;;
    only-one)
        take_selection
        ;;
    -h|--help|help|-help)
        echo "Usage:"
        echo "  $0           -> Take fullscreen screenshot"
        echo "  $0 only-one  -> Select area screenshot"
        ;;
    *)
        echo "Usage:"
        echo "  $0           -> Take fullscreen screenshot"
        echo "  $0 only-one  -> Select area screenshot"
        exit 1
        ;;
esac
