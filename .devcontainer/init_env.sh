#!/usr/bin/env bash
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

# sharing-git-credentials see https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials
init_ssh_agent(){
  if [[ -z "$SSH_AUTH_SOCK" || ! -S "$SSH_AUTH_SOCK" ]]; then
    RUNNING_AGENT="$(ps -ax | grep '''ssh-agent -s''' | grep -v grep | wc -l)"
    if [ "$RUNNING_AGENT" = "0" ]; then
        ssh-agent -s &> $HOME/.ssh/ssh-agent
    fi
    eval $(cat $HOME/.ssh/ssh-agent) > /dev/null
    ssh-add 2> /dev/null
    echo $SSH_AUTH_SOCK
fi
# Define code block to insert (with unique identifier comment)
SSH_AGENT_CODE='# SSH Agent Auto Management[ID:ssh_agent_v1]
if [[ -z "$SSH_AUTH_SOCK" || ! -S "$SSH_AUTH_SOCK" ]]; then
    RUNNING_AGENT="$(ps -ax | grep '\''ssh-agent -s'\'' | grep -v grep | wc -l)"
    if [ "$RUNNING_AGENT" = "0" ]; then
        ssh-agent -s &> $HOME/.ssh/ssh-agent
    fi
    eval $(cat $HOME/.ssh/ssh-agent) > /dev/null
    ssh-add 2> /dev/null
fi
# END_SSH_AGENT_CODE'

TARGET_FILE="$HOME/.bashrc"

# Create .ssh directory if not exists
mkdir -p "$HOME/.ssh"

# Check for existing code block
if ! grep -q 'END_SSH_AGENT_CODE' "$TARGET_FILE"; then
    echo "Adding SSH agent management code to ${TARGET_FILE}..."
    echo "$SSH_AGENT_CODE" >> "$TARGET_FILE"
    if [[ "$SHELL" == *"zsh"* ]]; then
    echo "$SSH_AGENT_CODE" >> "$HOME/.zshrc"
    fi
    echo "Code added successfully. Please run source ${TARGET_FILE} to apply changes immediately"
else
    echo "Existing SSH agent code detected, no need to add again"
fi
}
init_ssh_agent
mkdir -p models