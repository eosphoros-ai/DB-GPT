#!/bin/bash
set -e
cd /app

# Install Oh My Zsh with mirror fallback
if [ ! -f ~/.oh-my-zsh/oh-my-zsh.sh ]; then
  echo "Installing Oh My Zsh..."
  REPO=mirrors/oh-my-zsh REMOTE=https://gitee.com/mirrors/oh-my-zsh.git sh -c "$(curl -fsSL https://gitee.com/mirrors/oh-my-zsh/raw/master/tools/install.sh)" "" --unattended
fi

# Install plugins with mirror switching
plugins=(
  "zsh-users/zsh-autosuggestions"
  "zsh-users/zsh-syntax-highlighting"
)

for plugin in "${plugins[@]}"; do
  repo_name=$(basename $plugin)
  if [ ! -d ~/.oh-my-zsh/custom/plugins/$repo_name ]; then
    echo "Installing plugin: $plugin"
    # Clone from GitHub with Gitee mirror fallback
    git clone --depth=1 https://github.com/$plugin.git ~/.oh-my-zsh/custom/plugins/$repo_name || \
    git clone --depth=1 https://gitee.com/zsh-users/$repo_name.git ~/.oh-my-zsh/custom/plugins/$repo_name
  fi
done 


# Install theme with mirror fallback
if [ ! -d ~/.oh-my-zsh/custom/themes/powerlevel10k ]; then
  echo "Installing powerlevel10k theme..."
  # Clone from GitHub with Gitee mirror fallback
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/.oh-my-zsh/custom/themes/powerlevel10k || \
  git clone --depth=1 https://gitee.com/romkatv/powerlevel10k.git ~/.oh-my-zsh/custom/themes/powerlevel10k
fi

# Configuration section remains the same...
# Apply custom configuration
if [ -f /app/.devcontainer/zshrc-config ]; then
  cp /app/.devcontainer/zshrc-config ~/.zshrc
else
  # Generate basic .zshrc if no custom configuration exists
  cat << EOF >> ~/.zshrc
export ZSH="\$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"
plugins=(git zsh-autosuggestions zsh-syntax-highlighting autojump)
source \$ZSH/oh-my-zsh.sh

# Enable autojump
[[ -s /usr/share/autojump/autojump.sh ]] && source /usr/share/autojump/autojump.sh
EOF
fi

# Ensure autojump configuration is applied (even if custom configuration exists)
if ! grep -q "autojump.sh" ~/.zshrc; then
  echo '[[ -s /usr/share/autojump/autojump.sh ]] && source /usr/share/autojump/autojump.sh' >> ~/.zshrc
fi
cat << EOF >> ~/.zshrc
# Add the following to ~/.zshrc
load_env() {
    if [ -f /app/.env ]; then
        ENV_CONTENT=$(grep -vE '^#|^$' /app/.env | xargs)
        if [ -n "$ENV_CONTENT" ]; then
          export $ENV_CONTENT
        fi
    fi
}
load_env
EOF
rm -rf .venv.make
echo "Post-create setup completed!"