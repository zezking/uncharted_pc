#!/usr/bin/env bash
# Opens the port's own GTK4 launcher (bb-launcher.sh, adapted for Uncharted: game picker,
# vblank, settings in ~/.config/uncharted-launcher/settings.json).
exec bash "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/launcher/bb-launcher.sh" "$@"
