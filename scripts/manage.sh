#!/bin/sh
# Run on the Umbrel host, from an extracted release. No downloads or network calls.
set -eu
action=${1:-check}
container=${2:-solobch-forge_server_1}
case "$action" in check|install|restore) ;; *) echo 'Usage: sudo sh scripts/manage.sh check|install|restore [container]' >&2; exit 2;; esac
case "$container" in ''|*[!a-zA-Z0-9_.-]*) echo 'Invalid container name' >&2; exit 2;; esac
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v docker >/dev/null 2>&1 || { echo 'Docker is required; run this on your Umbrel host.' >&2; exit 1; }
docker inspect "$container" >/dev/null
running=$(docker inspect --format '{{.State.Running}}' "$container")
[ "$running" = true ] || { echo 'Forge must be running for this operation.' >&2; exit 1; }
for file in dashboard.html compatibility.json scripts/dashboard_installer.py; do
    [ -f "$package_dir/$file" ] || { echo "Missing release file: $file" >&2; exit 1; }
done
# Stage files in the existing private app volume; no ports or permissions changed.
docker exec -u 0 "$container" mkdir -p /data/solobch-dashboard-release/scripts
docker cp "$package_dir/dashboard.html" "$container:/data/solobch-dashboard-release/dashboard.html"
docker cp "$package_dir/compatibility.json" "$container:/data/solobch-dashboard-release/compatibility.json"
docker cp "$package_dir/scripts/dashboard_installer.py" "$container:/data/solobch-dashboard-release/scripts/dashboard_installer.py"
docker exec -u 0 "$container" python3 /data/solobch-dashboard-release/scripts/dashboard_installer.py "$action"
if [ "$action" != check ]; then
    echo 'Restarting Forge; connected miners will briefly disconnect.'
    docker restart "$container"
    echo 'Refresh the dashboard. Confirm CONNECTED, a synced node, and new accepted shares.'
fi
