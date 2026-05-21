#!/usr/bin/env bash
# One-time setup for the beta-watch launchd job.
# Run from anywhere: ./tools/beta-watch/install.sh
#
# What this does:
#   1. chmod +x on the watcher scripts
#   2. Copies the plist into ~/Library/LaunchAgents
#   3. Loads it via launchctl (starts the 30-min poll)
#
# What it does NOT do (you do these yourself, once):
#   - Install SteamCMD (already at ~/Steam/steamcmd.sh per user)
#   - Cache Steam Guard credentials. First time, run:
#       ~/Steam/steamcmd.sh +login YOUR_USERNAME YOUR_PASSWORD
#     and enter the Steam Guard code. SteamCMD remembers the session.
#   - Populate 1Password items:
#       op://Spire Codex/Steam/username
#       op://Spire Codex/Steam/password
#       op://Spire Codex/Discord Webhooks/beta-watch
#   - Opt the Steam account into the StS2 beta branch once via the GUI.

set -euo pipefail

REPO=$(cd "$(dirname "$0")/../.." && pwd)
WATCH_DIR="$REPO/tools/beta-watch"
LABEL="com.spirecodex.beta-watch"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "[1/3] making scripts executable"
chmod +x "$WATCH_DIR/watch.sh" "$WATCH_DIR/process.sh"

echo "[2/3] installing launchd plist to $PLIST_DST"
mkdir -p "$HOME/Library/LaunchAgents"
cp "$WATCH_DIR/$LABEL.plist" "$PLIST_DST"

echo "[3/3] loading launchd job"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo ""
echo "✓ beta-watch installed and running."
echo "  Logs:   ~/.spire-codex/beta-watch/watch.log"
echo "  State:  ~/.spire-codex/beta-watch/last-buildid"
echo ""
echo "Trigger a manual run (e.g. to verify your 1Password + Steam creds):"
echo "  launchctl start $LABEL"
echo ""
echo "Disable temporarily:"
echo "  launchctl unload $PLIST_DST"
