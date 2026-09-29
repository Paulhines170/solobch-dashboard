# SoloBCH Dashboard

A black-and-BCH-green dashboard add-on for **SoloBCH Forge 1.1.3 on Umbrel**.

**Experimental community add-on.** This replaces Forge's dashboard and adds a small, bounded record of accepted-share difficulty. It is not a mining pool, a standalone Umbrel app, or an official Forge/Umbrel product. You must already have SoloBCH Forge installed and mining successfully.

## See it first

Download and open [demo.html](demo.html) in a browser. The demo uses fictional data, makes no network requests, and cannot mine or change your pool.

## Features

- **Overview:** hashrate and history, workers, session information, and node status.
- **Recent Share History:** lifetime acceptance statistics, the latest accepted shares, and a bar per share's actual achieved difficulty.
- **Block Hunter:** last share, recent best, lifetime best, and the current block target on a logarithmic scale. This is a comparison, not accumulated progress toward finding a block.
- **Blocks found:** recorded block status/confirmations and a solo-mining outlook.
- Black background, BCH-green charts, shaded hashrate history, and 1H / 3H / 24H views.
- Five-second status refresh, a clear disconnected/stale state, and existing Umbrel authentication.

## Compatibility and limits

| Item | Support |
| --- | --- |
| SoloBCH Forge | 1.1.3 only; source compatibility is checked before patching |
| Host | Umbrel with Docker access and the Forge app already installed |
| Default container | `solobch-forge_server_1` |
| Dashboard URL | Your existing Forge app URL; no new public port |
| Node / miners | Existing configuration remains in place |
| Recent share chart | Latest 100 accepted shares across currently connected workers |
| Share retention | At most 512 shares per connection in RAM; resets on restart or reconnect |
| Hashrate history | Existing Forge history; availability/retention depends on Forge |
| Updates | Container recreation or Forge updates can remove this add-on |

The 24-hour hashrate button does **not** imply 24-hour individual-share retention. Rejected shares are counted but do not appear in the accepted-share log. "Recent best" means the best of the latest 100 retained shares, not a 24-hour best. Network percentage uses the current difficulty. Chart averages use available samples and are not guaranteed to cover the full selected interval.

No mining validation, payout-address, coinbase, or block-submission code is intentionally changed. The telemetry additions are checked for reversibility, and tests verify that assigned-work accounting remains unchanged. This does not certify Forge's mining correctness or guarantee block acceptance or rewards.

## Installation

Use a trusted copy of this repository/release. There is no remote `curl | sh` installer. Keep Umbrel and Forge private; GitHub hosts the source code, not your node.

1. On GitHub, choose **Code → Download ZIP** (or download a release archive).
2. Extract it on your computer. Transfer the extracted folder to your Umbrel using SCP or an SFTP client. For example, from the folder's parent on your computer:

   ```sh
   scp -r solobch-dashboard-main umbrel@YOUR_UMBREL_IP:~/
   ```

   Replace the folder name with the one you actually extracted, and `YOUR_UMBREL_IP` with your Umbrel address.

3. In the **Umbrel terminal**, enter the uploaded folder:

   ```sh
   cd ~/solobch-dashboard-main
   ```

4. Check compatibility. This stages the release in the app's data volume but does not patch or restart Forge:

   ```sh
   sudo sh scripts/manage.sh check
   ```

5. If the check passes, install:

   ```sh
   sudo sh scripts/manage.sh install
   ```

   This backs up the two affected source files, applies the patch, then restarts Forge. Miners will briefly disconnect. Stop if any command reports an error; do not ignore compatibility failures.

6. Open Forge normally through Umbrel and hard-refresh the page. Check **CONNECTED**, a synced node, and increasing accepted shares. New difficulty bars appear as accepted shares arrive. Allow the hashrate averaging windows to refill after restart.

If your container has a different name, pass it as the second argument:

```sh
sudo sh scripts/manage.sh check YOUR_FORGE_CONTAINER
sudo sh scripts/manage.sh install YOUR_FORGE_CONTAINER
```

## Uninstall / roll back

From the same uploaded folder:

```sh
sudo sh scripts/manage.sh restore
```

This restores the files saved immediately before the latest successful install and restarts Forge. If another dashboard customization was present then, it restores that customization. Backup checksums and current-source checks prevent overwriting unrelated changes.

If Forge will not start, or installation was interrupted, see [Recovery](docs/RECOVERY.md). Do not repeatedly install over an unexplained failure.

## What gets changed

The installer changes only `/app/server/status.py` (the dashboard template) and `/app/server/stratum.py` (three telemetry insertions). It stages the release under `/data/solobch-dashboard-release` and saves backups under `/data/solobch-dashboard-backups`, inside Forge's existing persistent data volume. It does not edit wallet configuration, node credentials, mining addresses, Docker networks, published ports, or Umbrel authentication.

The source changes live in the container's writable layer, so they survive an ordinary restart but **not necessarily a container recreation or app update**. Only reapply to a supported version after running `check`. Retained backups are not automatically deleted.

## Development and validation

No build step or third-party frontend dependencies are required. The distributable dashboard is `dashboard.html`; the installer uses Python's standard library.

```sh
python3 -m unittest discover -s tests -v
node scripts/check_dashboard.cjs
```

Tests cover source compatibility, bounded telemetry, preserving accounting, install/restore, repeated installs, interrupted updates, and refusing to overwrite unrelated source changes. A synthetic-data browser check was performed during development. End-to-end block discovery/payout, every miner model, and every Umbrel hardware variant have **not** been tested.

## Attribution

Built for [SoloBCH Forge by DanCreatesStuff](https://github.com/DanCreatesStuff/SoloBCHForge). Forge remains the mining backend. This project includes upstream fixture files and derives its telemetry integration from Forge's MIT-licensed code. See [LICENSE](LICENSE), [LICENSE-Forge](LICENSE-Forge), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Reporting issues

Include the Forge version, dashboard version, browser, and the exact error. Remove wallet addresses, worker IPs, RPC credentials, cookies, and other personal data from logs and screenshots before posting. Never share a wallet recovery phrase or private key.
