#!/bin/bash
# Doppelklick im Finder startet Jarvis Stimme mit Fenster.
cd "$(dirname "$0")" || exit 1
exec ./jarvis-stimme.sh --gui "$@"
