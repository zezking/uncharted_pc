#!/usr/bin/env bash
# Uncharted: The Nathan Drake Collection — zenity 4 game picker (bb-gui.sh style).
# Saves the choice to ~/.config/uncharted-launcher/settings.json and starts uncharted.sh.
set -euo pipefail
PORT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/uncharted-launcher
CONFIG=$CONFIG_DIR/settings.json
mkdir -p "$CONFIG_DIR"

# Current settings (defaults: u1, 60 Hz, windowed)
exe=u1; hz=60; fs=false
[[ -f $CONFIG ]] && eval "$(python3 - "$CONFIG" <<'EOF'
import json, sys
try: d = json.load(open(sys.argv[1]))
except Exception: d = {}
print('exe=%s' % ('u%d' % d.get('exe', 1) if isinstance(d.get('exe'), int) else d.get('exe', 'u1')))
print('hz=%s' % d.get('vblank', 60)); print('fs=%s' % ('true' if d.get('fullscreen') else 'false'))
EOF
)"

if ! ans=$(zenity --forms --title='Uncharted: The Nathan Drake Collection' \
        --text='Pick a game and options' \
        --add-list='Game|Game' --show-header \
        --list-values="Drake's Fortune (U1)|Among Thieves (U2)|Drake's Deception (U3)|Collection menu (launcher)" \
        --add-combo='Frame rate' --combo-values="$hz|60|120" \
        --add-combo='Display' --combo-values="$([ "$fs" = true ] && echo 'Fullscreen|Windowed' || echo 'Windowed|Fullscreen')"); then
    rc=$?
    # 1 = user cancelled; anything else is a real error worth showing
    [[ $rc -eq 1 ]] && exit 0
    zenity --error --text="zenity failed (rc=$rc)" 2>/dev/null || true
    exit 1
fi

game=$(awk -F'|' '{print $1}' <<<"$ans")
sel_hz=$(awk -F'|' '{print $2}' <<<"$ans")
fullscreen=$(awk -F'|' '{print $3}' <<<"$ans")

case "$game" in
    "Drake's Fortune (U1)")       exe=u1 ;;
    "Among Thieves (U2)")         exe=u2 ;;
    "Drake's Deception (U3)")     exe=u3 ;;
    "Collection menu (launcher)") exe=u1 ;;
    *) exe=u1 ;;
esac

python3 - "$CONFIG" "$exe" "$sel_hz" "$fullscreen" <<'EOF'
import json, sys
cfg = {}
try: cfg = json.load(open(sys.argv[1]))
except Exception: pass
cfg.update(exe=sys.argv[2], vblank=int(sys.argv[3]),
           fullscreen=(sys.argv[4].strip().lower() == 'fullscreen'))
json.dump(cfg, open(sys.argv[1], 'w'), indent=2)
EOF

exec "$PORT_DIR/uncharted.sh"
