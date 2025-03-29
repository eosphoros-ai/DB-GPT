# Developing inside a Container
Use VS Code's ​Dev Container extension to build a containerized development environment. Leverage the eosphorosai/dbgpt:latest image as the development environment to avoid repeated dependency installations and improve development efficiency.  
NOTE: **Compatible with Linux and Windows Subsystem for Linux (WSL) environments only.**
# Setup

- Follow the guide [Developing inside a Container](https://code.visualstudio.com/docs/devcontainers/containers) to set up the Dev Container:  
  - Install the ​**Dev Containers** extension.   

- Before the first launch, please execute the .devcontainer/init_env.sh script in the project root directory in **host**  
- Create `models` dir in project root and download text2vec-large-chinese to models/text2vec-large-chinese
- Use the shortcut `Ctrl+Shift+P` to open the command palette, then enter `Dev Containers: Open Folder in Container`.

# Develop  
After successfully starting the Dev Container, open the terminal    

- Activate the virtual environment
```bash
. /opt/.uv.venv/bin/activate
```

- Customize the configuration file  

You can copy the configuration file to the `.devcontainer` directory and rename it to `dev.toml` to avoid committing your personal configurations to the repository. 
```bash
cp configs/dbgpt-app-config.example.toml .devcontainer/dev.toml
```

- Start the service

```bash
dbgpt start webserver --config .devcontainer/dev.toml
```

# Create A Pull Request

Please refer to [CONTRIBUTING.md](../CONTRIBUTING.md). Before executing the make script or git commit, remember to deactivate the current virtual environment in the development environment.
