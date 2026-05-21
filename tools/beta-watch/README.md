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
# 1. Cache Steam Guard auth (interactive, only required once per machine)
~/Steam/steamcmd.sh +login YOUR_USERNAME YOUR_PASSWORD
# Enter your Steam Guard code when prompted; SteamCMD remembers the session.

# 2. Opt the Steam account into the StS2 beta branch via the regular Steam
#    GUI: StS2 → Properties → Betas → pick the beta branch from the dropdown.

# 3. Populate 1Password items in the "Spire Codex" vault:
#    - Steam item with fields: username, password
#    - Discord Webhooks item with field: beta-watch (webhook URL)

# 4. Beta branch defaults to "public-beta" (what Mega Crit uses). If they
#    rename it, set SPIRE_BETA_BRANCH in the launchd plist's
#    EnvironmentVariables block, or edit watch.sh's default.

# 5. Install the launchd job
./tools/beta-watch/install.sh
```

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
