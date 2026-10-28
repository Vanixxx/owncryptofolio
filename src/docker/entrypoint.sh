#!/bin/sh
# Starts as root only to hand the mounted folders to the app's user, then drops root for good.
# Docker and Unraid create a missing host folder as root, and the app could not write its keys
# there. PUID/PGID choose the user (Unraid's convention: 99/100); default the image's user 1000.
set -e
if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-1000}"
  PGID="${PGID:-1000}"
  for dir in /data "${BACKUP_DIR:-/backups}"; do
    mkdir -p "$dir"
    # only a folder that is not the user's yet is walked, not a full one on every start
    if [ "$(stat -c %u "$dir")" != "$PUID" ]; then
      echo "entrypoint: handing $dir to $PUID:$PGID"
      chown -R "$PUID:$PGID" "$dir"
    fi
  done
  exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups -- "$@"
fi
# started with --user: nothing to hand over
exec "$@"
