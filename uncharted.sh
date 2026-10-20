#!/usr/bin/env bash
# Launch Uncharted: The Nathan Drake Collection through the Linux port, with the settings
# saved by uncharted-gui.sh (~/.config/uncharted-launcher/settings.json).
#
# Usage: uncharted.sh [u1|u2|u3] [extra bb-probe args]
#   u1 = Drake's Fortune (collection launcher eboot), u2 = Among Thieves, u3 = Drake's Deception
# Env: BB_* variables win over the saved settings; UC_GAME_DIR overrides the game folder.
# Expects the decrypted dump (CUSA02320) at ../game/CUSA02320/Image0 next to this checkout.
set -euo pipefail
PORT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GAME="${UC_GAME_DIR:-$PORT/../game/CUSA02320/Image0}"
CONFIG=${XDG_CONFIG_HOME:-$HOME/.config}/uncharted-launcher/settings.json

if [[ ! -f $GAME/eboot.bin ]]; then
    echo "No eboot.bin in $GAME (set UC_GAME_DIR to the decrypted dump)." >&2; exit 1
fi
export BB_GAME_DIR="$GAME"

if [[ -f $CONFIG ]]; then
    exe=$(python3 -c 'import json;print(json.load(open("'"$CONFIG"'")).get("exe","u1"))' 2>/dev/null || echo u1)
    fs=$(python3 -c 'import json;print(json.load(open("'"$CONFIG"'")).get("fullscreen",False))' 2>/dev/null || echo False)
    hz=$(python3 -c 'import json;print(json.load(open("'"$CONFIG"'")).get("vblank",60))' 2>/dev/null || echo 60)
    export BB_EXE="${BB_EXE:-${1:-$exe}}"
    if [[ -z ${BB_FULLSCREEN:-} && $fs == True ]]; then export BB_FULLSCREEN=1; fi
    export BB_VBLANK_HZ="${BB_VBLANK_HZ:-$hz}"
else
    export BB_EXE="${BB_EXE:-${1:-u1}}"
fi
case "${1:-}" in u1|u2|u3) shift;; esac

cd "$PORT"
exec ./run.sh "$@"
