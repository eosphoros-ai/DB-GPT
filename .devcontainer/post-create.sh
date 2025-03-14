#!/bin/bash
set -e
cd /app
# Install Oh My Zsh
if [ ! -d ~/.oh-my-zsh ]; then
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
fi

# Install plugins
plugins=(
  "zsh-users/zsh-autosuggestions"
  "zsh-users/zsh-syntax-highlighting"
)

for plugin in "${plugins[@]}"; do
  repo_name=$(basename $plugin)
  if [ ! -d ~/.oh-my-zsh/custom/plugins/$repo_name ]; then
    git clone --depth=1 https://github.com/$plugin.git ~/.oh-my-zsh/custom/plugins/$repo_name
  fi
done

# Install theme
if [ ! -d ~/.oh-my-zsh/custom/themes/powerlevel10k ]; then
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/.oh-my-zsh/custom/themes/powerlevel10k
fi

# Apply custom configuration
if [ -f /workspace/.devcontainer/zshrc-config ]; then
  cp /workspace/.devcontainer/zshrc-config ~/.zshrc
else
  # Generate basic .zshrc if no custom configuration exists
  cat << EOF > ~/.zshrc
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
if [ -f /app/.env ]; then
  export $(grep -vE '^#|^$' /app/.env | xargs)
fi
EOF
rm -rf .venv.make
echo "Post-create setup completed!"