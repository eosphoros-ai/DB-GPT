#!/usr/bin/env bash
set -euo pipefail

OS=$(uname -s)
USERNAME="$USER"
USER_UID=$(id -u "$USER")

if [ "$OS" = "Linux" ]; then
  GROUPNAME=$(id -gn "$USER")
  USER_GID=$(id -g "$USER")
else
  GROUPNAME="root"
  USER_GID="0"
fi


printf "OS=%s\nUSERNAME=%s\nUSER_UID=%s\nGROUPNAME=%s\nUSER_GID=%s\n" \
  "$OS" \
  "$USERNAME" \
  "$USER_UID" \
  "$GROUPNAME" \
  "$USER_GID" > .devcontainer/.env
