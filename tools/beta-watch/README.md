# beta-watch

Automated detection + ingestion of new StS2 beta builds. A launchd job fires
`watch.sh` every 15 minutes on Thursdays from 15:00 to 22:45 local — Mega
Crit's typical beta-drop window. Manually trigger any time with
`launchctl start com.spirecodex.beta-watch`. The watcher:

1. Has SteamCMD sync the StS2 beta branch (no-op if up to date)
2. Reads the buildid from `appmanifest_2868840.acf`
3. If buildid changed, runs `process.sh`:
   - Godot RE Tools extracts assets from the `.pck`
   - ilspycmd decompiles `sts2.dll`
   - Sniffs the version string from the decompiled C#
   - Archives the `.dll` + `.pck` under `extraction/beta/archives/`
   - Runs `parse_all.py` into `data-beta/<version>/`
   - Runs `diff_data.py` against the previous beta to generate a changelog
   - Re-points the `data-beta/latest` symlink
   - Pushes a branch and opens a PR on a new branch `auto/beta-<version>`
4. Sends a Discord webhook with the new version + PR URL

The watcher is idempotent. If a tick fails partway, the next tick retries
from scratch — `last-buildid` is only updated on full success.

## One-time setup

```bash
# 1. Cache Steam Guard auth — interactive, ONE TIME per machine.
#    SteamCMD writes a session token to ~/Library/Application Support/Steam
#    so future headless runs only need the username (no password).
~/Steam/steamcmd.sh +login YOUR_USERNAME
# Enter your password and Steam Guard code at the prompts, then type `quit`.
# From now on, `+login YOUR_USERNAME` alone works.

# 2. Opt the Steam account into the public-beta branch via the regular Steam
#    GUI: StS2 → Properties → Betas → pick `public-beta` from the dropdown.

# 3. Scaffold the local config file:
./tools/beta-watch/install.sh
# First run creates ~/.spire-codex/beta-watch/config.env (a template) and
# exits. Edit it to set STEAM_USER and DISCORD_URL, then re-run install.sh.

# 4. Generate a Discord webhook (if you want pings): in your Discord
#    channel → Edit Channel → Integrations → Webhooks → New Webhook →
#    Copy Webhook URL. Paste into config.env's DISCORD_URL.

# 5. Re-run install.sh — this time it loads the launchd plist.
./tools/beta-watch/install.sh
```

The config file at `~/.spire-codex/beta-watch/config.env` lives outside the
git repo, so it can't be committed by accident and `git pull` can never
overwrite it. The earlier design used the 1Password CLI but `op` prompts
for Touch ID when the desktop app auto-locks, which kills unattended
launchd runs.

## Useful commands

```bash
# Trigger a manual run (handy for verifying credentials)
launchctl start com.spirecodex.beta-watch

# Watch the log live
tail -f ~/.spire-codex/beta-watch/watch.log

# Disable temporarily
launchctl unload ~/Library/LaunchAgents/com.spirecodex.beta-watch.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.spirecodex.beta-watch.plist

# Force re-ingest of the current beta (clears last-seen state)
rm ~/.spire-codex/beta-watch/last-buildid
launchctl start com.spirecodex.beta-watch
```

## Configuration

All knobs are env vars with defaults that work on the current Mac:

| Var                  | Default                                        | Purpose                          |
|----------------------|------------------------------------------------|----------------------------------|
| `SPIRE_APP_ID`       | `2868840`                                      | Slay the Spire 2 Steam app id    |
| `SPIRE_BETA_BRANCH`  | `public-beta`                                  | Steam beta branch name           |
| `SPIRE_STEAMCMD`     | `$HOME/Steam/steamcmd.sh`                      | Path to SteamCMD binary          |
| `SPIRE_STATE_DIR`    | `$HOME/.spire-codex/beta-watch`                | Where state + logs live          |
| `SPIRE_REPO`         | `$HOME/Documents/Projects/spire-codex`         | Repo working tree                |

## What gets reviewed manually

The PR opened by `process.sh` is intentionally *not* auto-merged. Game
schema changes can produce parser misfires (empty changelog files, missing
entity types, broken descriptions), and an auto-merge would push that to
production before anyone notices. Inspect the changelog files under
`data-beta/<version>/changelogs/` and the diff against `data-beta/latest`
before merging.

After merge, deploy beta with:

```bash
cd infrastructure/ansible && ./bin/do-ansible playbooks/deploy.yml \
  -e compose_file=docker-compose.beta.yml
```
