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

print_usage() {
    echo "Usage:"
    echo "  $0           -> Take screenshot for all screens in one save"
    echo "  $0 only-one  -> Click = selected screen, drag = selected area"
}

is_wayland() {
    [ "${XDG_SESSION_TYPE:-}" = "wayland" ]
}

take_fullscreen() {
    local file="$DIR/tam-ekran-$(date +%Y%m%d-%H%M%S).png"

    if is_wayland && command -v grim >/dev/null 2>&1; then
        grim "$file"
    elif command -v scrot >/dev/null 2>&1; then
        scrot "$file"
    else
        echo "No working screenshot tool found (need grim or scrot)" >&2
        exit 1
    fi

    notify_ok "All Screens"
    printf '%s\n' "$file"
}

take_wayland_selected_or_monitor() {
    local geom
    geom="$(slurp 2>/dev/null || true)"
    [ -z "$geom" ] && exit 0

    local pos_part size_part x y w h
    pos_part="${geom%% *}"
    size_part="${geom#* }"

    x="${pos_part%,*}"
    y="${pos_part#*,}"
    w="${size_part%x*}"
    h="${size_part#*x}"

    case "$x" in ''|*[!0-9]*) exit 0 ;; esac
    case "$y" in ''|*[!0-9]*) exit 0 ;; esac
    case "$w" in ''|*[!0-9]*) exit 0 ;; esac
    case "$h" in ''|*[!0-9]*) exit 0 ;; esac

    # Tek tık gibi küçük seçimse, Hyprland varsa seçilen monitörün tamamını çek
    if [ "$w" -le 5 ] || [ "$h" -le 5 ]; then
        if command -v hyprctl >/dev/null 2>&1; then
            local output_name
            output_name="$(
                hyprctl monitors -j 2>/dev/null | python3 -c '
import sys, json

x = int(sys.argv[1])
y = int(sys.argv[2])

try:
    mons = json.load(sys.stdin)
except Exception:
    sys.exit(1)

for m in mons:
    mx = int(m.get("x", 0))
    my = int(m.get("y", 0))
    mw = int(m.get("width", 0))
    mh = int(m.get("height", 0))

    if mx <= x < mx + mw and my <= y < my + mh:
        print(m.get("name", ""))
        sys.exit(0)

sys.exit(1)
' "$x" "$y"
            )"

            if [ -n "${output_name:-}" ]; then
                local file="$DIR/tam-ekran-$(date +%Y%m%d-%H%M%S).png"
                grim -o "$output_name" "$file"
                notify_ok "Selected Screen"
                printf '%s\n' "$file"
                return
            fi
        fi
    fi

    # Normal alan seçimi
    local file="$DIR/secili-alan-$(date +%Y%m%d-%H%M%S).png"
    grim -g "$geom" "$file"
    notify_ok "Selected Area"
    printf '%s\n' "$file"
}

take_selection() {
    if is_wayland && command -v grim >/dev/null 2>&1 && command -v slurp >/dev/null 2>&1; then
        take_wayland_selected_or_monitor
    elif command -v scrot >/dev/null 2>&1; then
        local file="$DIR/secili-alan-$(date +%Y%m%d-%H%M%S).png"
        scrot -s "$file"
        notify_ok "Selected Area"
        printf '%s\n' "$file"
    else
        echo "No working area screenshot tool found (need grim+slurp or scrot)" >&2
        exit 1
    fi
}

case "$ARG" in
    "")
        take_fullscreen
        ;;
    only-one)
        take_selection
        ;;
    -h|--help|help|-help)
        print_usage
        exit 0
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
