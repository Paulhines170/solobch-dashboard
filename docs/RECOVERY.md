# Recovery

These instructions target the default container name, `solobch-forge_server_1`. Substitute your container name if different. Backups do not include wallets or node data: this add-on never changes those.

## Forge is running

From your uploaded release folder on the Umbrel host:

```sh
sudo sh scripts/manage.sh restore
```

Restore checks both source files and backup hashes. It restores the files saved immediately before the most recent install. An interrupted install has a `prepared` journal; restore accepts each source file in either its before or after state.

## Forge cannot stay running

Do not delete the app or its data volume. Do not reset mining statistics.

The persistent backup directory is `/data/solobch-dashboard-backups` inside the Forge container. On the host it is normally inside the Forge app-data directory. To locate the mount without exposing credentials:

```sh
sudo docker inspect solobch-forge_server_1 --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Find the host path mapped to `/data`. Open its `solobch-dashboard-backups/current.json`. The `directory` value names the latest backup folder, containing `status.py` and `stratum.py`. The manifest contains each file's `before` SHA-256 checksum. Verify those checksums with `sha256sum` before restoring.

If you are unsure which folder is correct, ask for help with the error and manifest, not your entire config file. To copy verified backups into a stopped container, use `docker cp` with the **actual paths** you identified, one file at a time, then start Forge. Do not copy unrelated versions of these files.

Docker copying works with stopped containers. If the container itself was recreated by an Umbrel app update, do not copy old Python files into a new Forge version. Prefer the stock app version installed by Umbrel and wait for a compatible add-on release.

## Install fails compatibility checks

Nothing in the running source is intentionally patched until all compatibility checks and compilation checks pass. The staged release files may have been copied to `/data`. Use the Forge version identified in the README or leave the stock dashboard in place. Do not disable the checks.

## Old dashboard still appears

Hard-refresh the browser and check that the installer reported success and Forge restarted. If the container was recreated, the customization may have been removed; check compatibility before reapplying.

## No recent-share bars

This history starts after the telemetry patch is running. Ensure your miner has reconnected and the accepted-share count increases. A miner reconnect or Forge restart clears its recent-share buffer; lifetime counters and Forge's own hashrate history are separate.
