#!/usr/bin/env bash
# One-time setup for the beta-watch launchd job.
# Run from anywhere: ./tools/beta-watch/install.sh
#
# What this does:
#   1. chmod +x on the watcher scripts
#   2. Scaffolds ~/.spire-codex/beta-watch/config.env (gitignored by location)
#   3. Copies the plist into ~/Library/LaunchAgents
#   4. Loads it via launchctl (arms the calendar schedule)
#
# What it does NOT do (you do these yourself, once):
#   - Install SteamCMD (already at ~/Steam/steamcmd.sh per user)
#   - Cache Steam Guard credentials. First time, run:
#       ~/Steam/steamcmd.sh +login YOUR_USERNAME
#     enter password + Steam Guard code, then `quit`. SteamCMD caches the
#     session token, so the watcher only needs the username going forward.
#   - Edit ~/.spire-codex/beta-watch/config.env to fill in STEAM_USER and
#     (optional) DISCORD_URL — install.sh scaffolds it empty.
#   - Opt the Steam account into the StS2 public-beta branch once via the GUI.

set -euo pipefail

REPO=$(cd "$(dirname "$0")/../.." && pwd)
WATCH_DIR="$REPO/tools/beta-watch"
LABEL="com.spirecodex.beta-watch"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
STATE_DIR="$HOME/.spire-codex/beta-watch"
CONFIG="$STATE_DIR/config.env"

echo "[1/4] making scripts executable"
chmod +x "$WATCH_DIR/watch.sh" "$WATCH_DIR/process.sh"

echo "[2/4] scaffolding config at $CONFIG (skipped if it already exists)"
mkdir -p "$STATE_DIR"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" <<'TEMPLATE'
# Beta-watch credentials. NEVER commit this file — it lives outside the
# git repo on purpose. Edit the two values below, then save.

# Your Steam username (NOT email). SteamCMD must already have a cached
# session for this account (run: ~/Steam/steamcmd.sh +login THIS_USER
# interactively once, enter your password + Steam Guard code, then quit).
STEAM_USER=""

# Discord webhook URL where new-beta pings get posted. Leave empty to
# disable Discord notifications entirely (the pipeline still opens a PR).
# Generate one in your Discord server: channel → Edit → Integrations →
# Webhooks → New Webhook → Copy Webhook URL.
DISCORD_URL=""
TEMPLATE
  echo "    → created template. EDIT IT NOW and re-run install.sh to load the plist."
  chmod 600 "$CONFIG"
  exit 0
fi

# Validate the config has at least STEAM_USER set so we fail loud here
# instead of letting launchd produce a confusing exit-2 on first fire.
# shellcheck source=/dev/null
source "$CONFIG"
if [ -z "${STEAM_USER:-}" ]; then
  echo "    → $CONFIG exists but STEAM_USER is empty. Fill it in and re-run."
  exit 1
fi

echo "[3/4] installing launchd plist to $PLIST_DST"
mkdir -p "$HOME/Library/LaunchAgents"
cp "$WATCH_DIR/$LABEL.plist" "$PLIST_DST"

echo "[4/4] loading launchd job"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo ""
echo "✓ beta-watch installed and running."
echo "  Config: $CONFIG"
echo "  Logs:   $STATE_DIR/watch.log"
echo "  State:  $STATE_DIR/last-buildid"
echo ""
echo "Trigger a manual run (e.g. to verify your Steam creds):"
echo "  launchctl start $LABEL"
echo ""
echo "Disable temporarily:"
echo "  launchctl unload $PLIST_DST"
