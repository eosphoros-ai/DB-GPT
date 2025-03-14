import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Docker Deployment

## Docker image preparation

There are two ways to prepare a Docker image. 
1. Pull from the official image 
2. Build locally, see [Build Docker Image](./build_image.md) 

You can **choose any one** during actual use.


## Deploy With Proxy Model

In this deployment, you don't need an GPU environment.

1. Pull from the official image repository, [Eosphoros AI Docker Hub](https://hub.docker.com/u/eosphorosai)

```bash
docker pull eosphorosai/dbgpt-openai:latest
```

2. Run the Docker container

This example requires you previde a valid API key for the SiliconFlow API. You can obtain one by signing up at [SiliconFlow](https://siliconflow.cn/) and creating an API key at [API Key](https://cloud.siliconflow.cn/account/ak).


```bash
docker run -it --rm -e SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY} \
 -p 5670:5670 --name dbgpt eosphorosai/dbgpt-openai
```

Please replace `${SILICONFLOW_API_KEY}` with your own API key.


Then you can visit [http://localhost:5670](http://localhost:5670) in the browser.


## Deploy With GPU (Local Model)

In this deployment, you need an GPU environment.

Before running the Docker container, you need to install the NVIDIA Container Toolkit. For more information, please refer to the official documentation [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

In this deployment, you will use a local model instead of downloading it from the Hugging Face or ModelScope model hub. This is useful if you have already downloaded the model to your local machine or if you want to use a model from a different source.

### Step 1: Download the Model

Before running the Docker container, you need to download the model to your local machine. You can use either Hugging Face or ModelScope (recommended for users in China) to download the model.

<Tabs>
<TabItem value="modelscope" label="Download from ModelScope">

1. Install `git` and `git-lfs` if you haven't already:

   ```bash
   sudo apt-get install git git-lfs
   ```

2. Create a `models` directory in your current working directory:

   ```bash
   mkdir -p ./models
   ```

3. Use `git` to clone the model repositories into the `models` directory:

   ```bash
   cd ./models
   git lfs install
   git clone https://www.modelscope.cn/Qwen/Qwen2.5-Coder-0.5B-Instruct.git
   git clone https://www.modelscope.cn/BAAI/bge-large-zh-v1.5.git
   cd ..
   ```

   This will download the models into the `./models/Qwen2.5-Coder-0.5B-Instruct` and `./models/bge-large-zh-v1.5` directories.

</TabItem>
<TabItem value="huggingface" label="Download from Hugging Face">

1. Install `git` and `git-lfs` if you haven't already:

   ```bash
   sudo apt-get install git git-lfs
   ```

2. Create a `models` directory in your current working directory:

   ```bash
   mkdir -p ./models
   ```

3. Use `git` to clone the model repositories into the `models` directory:

   ```bash
   cd ./models
   git lfs install
   git clone https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct
   git clone https://huggingface.co/BAAI/bge-large-zh-v1.5
   cd ..
   ```

   This will download the models into the `./models/Qwen2.5-Coder-0.5B-Instruct` and `./models/bge-large-zh-v1.5` directories.

</TabItem>
</Tabs>

---

### Step 2: Prepare the Configuration File

Create a `toml` file named `dbgpt-local-gpu.toml` and add the following content:

```toml
[models]
[[models.llms]]
name = "Qwen2.5-Coder-0.5B-Instruct"
provider = "hf"
# Specify the model path in the local file system
path = "/app/models/Qwen2.5-Coder-0.5B-Instruct"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# Specify the model path in the local file system
path = "/app/models/bge-large-zh-v1.5"
```

This configuration file specifies the local paths to the models inside the Docker container.

---

### Step 3: Run the Docker Container

Run the Docker container with the local `models` directory mounted:

```bash
docker run --ipc host --gpus all \
  -it --rm \
  -p 5670:5670 \
  -v ./dbgpt-local-gpu.toml:/app/configs/dbgpt-local-gpu.toml \
  -v ./models:/app/models \
  --name dbgpt \
  eosphorosai/dbgpt \
  dbgpt start webserver --config /app/configs/dbgpt-local-gpu.toml
```

#### Explanation of the Command:
- `--ipc host`: Enables host IPC mode for better performance.
- `--gpus all`: Allows the container to use all available GPUs.
- `-v ./dbgpt-local-gpu.toml:/app/configs/dbgpt-local-gpu.toml`: Mounts the local configuration file into the container.
- `-v ./models:/app/models`: Mounts the local `models` directory into the container.
- `eosphorosai/dbgpt`: The Docker image to use.
- `dbgpt start webserver --config /app/configs/dbgpt-local-gpu.toml`: Starts the webserver with the specified configuration file.

---

### Step 4: Access the Application

Once the container is running, you can visit [http://localhost:5670](http://localhost:5670) in your browser to access the application.

---

### Step 5: Persist Data (Optional)

To ensure that your data is not lost when the container is stopped or removed, you can map the `pilot/data` and `pilot/message` directories to your local machine. These directories store application data and messages.

1. Create local directories for data persistence:

   ```bash
   mkdir -p ./pilot/data
   mkdir -p ./pilot/message
   mkdir -p ./pilot/alembic_versions
   ```

2. Modify the `dbgpt-local-gpu.toml` configuration file to point to the correct paths:

   ```toml
   [service.web.database]
   type = "sqlite"
   path = "/app/pilot/message/dbgpt.db"
   ```

3. Run the Docker container with the additional volume mounts:

   ```bash
   docker run --ipc host --gpus all \
     -it --rm \
     -p 5670:5670 \
     -v ./dbgpt-local-gpu.toml:/app/configs/dbgpt-local-gpu.toml \
     -v ./models:/app/models \
     -v ./pilot/data:/app/pilot/data \
     -v ./pilot/message:/app/pilot/message \
     -v ./pilot/alembic_versions:/app/pilot/meta_data/alembic/versions \
     --name dbgpt \
     eosphorosai/dbgpt \
     dbgpt start webserver --config /app/configs/dbgpt-local-gpu.toml
   ```

   This ensures that the `pilot/data` and `pilot/message` directories are persisted on your local machine.

---

### Summary of Directory Structure

After completing the steps, your directory structure should look like this:

```
.
├── dbgpt-local-gpu.toml
├── models
│   ├── Qwen2.5-Coder-0.5B-Instruct
│   └── bge-large-zh-v1.5
├── pilot
│   ├── data
│   └── message
```

This setup ensures that the models and application data are stored locally and mounted into the Docker container, allowing you to use them without losing data.
```

