#!/usr/bin/env bash
# Drive u1 past boot/title into the main menu via BB_PAD_FILE, so button-prompt
# textures upload to VRAM and land in the texdump. Run in background.
PAD=/tmp/uc-pad.txt
press() { echo "$1" > "$PAD"; sleep "${2:-0.35}"; : > "$PAD"; }
: > "$PAD"
sleep 30   # boot / legal
press cross
sleep 5
press cross
sleep 5
press options   # "press any button" screens
sleep 6
press options
sleep 6
press cross     # into main menu
# linger on main menu / move between entries so prompts render
sleep 8
press down
sleep 3
press up
sleep 45
