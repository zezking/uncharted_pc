#!/usr/bin/env bash
# Drive u1: boot -> title -> main menu -> load save -> in-game.
PAD=/tmp/uc-pad.txt
press() { echo "$1" > "$PAD"; sleep "${2:-0.35}"; : > "$PAD"; }
: > "$PAD"
sleep 30
press cross
sleep 5
press cross
sleep 5
press options
sleep 6
press options
sleep 6
press cross      # main menu: first entry (LOAD/CONTINUE)
sleep 4
press cross      # confirm save in list
sleep 55         # loading
press cross      # skip any prompt
sleep 10
press cross
sleep 30
press triangle   # pause? then back
sleep 2
press circle
sleep 40
