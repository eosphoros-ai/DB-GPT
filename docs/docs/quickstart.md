---
sidebar_position: 0
---
# Quickstart
DB-GPT supports the installation and use of a variety of open source and closed models. Different models have different requirements for environment and resources. If localized model deployment is required, GPU resources are required for deployment. The API proxy model requires relatively few resources and can be deployed and started on a CPU machine.


:::info note
- Detailed installation and deployment tutorials can be found in [Installation](/docs/installation).
- This page only introduces deployment based on ChatGPT proxy and local Vicuna model.
:::

## Environmental preparation

### Download source code

:::tip
Download DB-GPT
:::



```python
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

### Miniconda environment installation

- The default database uses SQLite, so there is no need to install a database in the default startup mode. If you need to use other databases, you can read the [advanced tutorials](/docs/application_manual/advanced_tutorial/rag) below. We recommend installing the Python virtual environment through the conda virtual environment. For the installation of Miniconda environment, please refer to the [Miniconda installation tutorial](https://docs.conda.io/projects/miniconda/en/latest/).

:::tip
Create a Python virtual environment
:::

```python
python >= 3.10
conda create -n dbgpt_env python=3.10
conda activate dbgpt_env

# it will take some minutes
pip install -e ".[default]"
```

:::tip
Copy environment variables
:::
```python
cp .env.template  .env
```

## Model deployment

:::info note

Provide two deployment methods to quickly start experiencing DB-GPT.

:::
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI', value: 'openai'},
    {label: 'Vicuna', value: 'vicuna'},
  ]}>

  <TabItem value="openai" label="openai">

:::info note

⚠️  You need to ensure that git-lfs is installed
```python
● CentOS installation: yum install git-lfs
● Ubuntu installation: apt-get install git-lfs
● MacOS installation: brew install git-lfs
```
:::

#### Install dependencies

```python
pip install  -e ".[openai]"
```

#### Download embedding model

```python
cd DB-GPT
mkdir models and cd models
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

#### Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=chatgpt_proxyllm
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
```
  </TabItem>

  <TabItem value="vicuna" label="vicuna">

#### Hardware requirements description
| Model    		                         |   Quantize   |  VRAM Size   	| 
|:----------------------------------------:|--------------:|---------------|
|Vicuna-7b     	                       |   4-bit      |  8GB         	|
|Vicuna-7b  		                       |   8-bit	    |  12GB        	|
|Vicuna-13b     	                     |   4-bit      |  12GB        	|
|Vicuna-13b                            |   8-bit      |  20GB         |

#### Download LLM

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large

# llm model, if you use openai or Azure or tongyi llm api service, you don't need to download llm model
git clone https://huggingface.co/lmsys/vicuna-13b-v1.5

```
#### Environment variable configuration, configure the LLM_MODEL parameter in the `.env` file
```python
# .env
LLM_MODEL=vicuna-13b-v1.5
```
  </TabItem>

</Tabs>


## Test data (optional)
Load default test data into SQLite database
- **Linux**

```python
bash ./scripts/examples/load_examples.sh
```
- **Windows**

```python
.\scripts\examples\load_examples.bat
```

## Run service

```python
python dbgpt/app/dbgpt_server.py
```

:::info NOTE
### Run service

If you are running version v0.4.3 or earlier, please start with the following command:

```python
python pilot/server/dbgpt_server.py
```
:::

## Visit website

#### 1. Production model:
Open the browser and visit [`http://localhost:5000`](http://localhost:5000)

#### 2. Development mode:
```
cd web & npm install
cp .env.template .env
// set the API_BASE_URL to your DB-GPT server address, it usually is http://localhost:5000
npm run dev
```
Open the browser and visit [`http://localhost:3000`](http://localhost:3000)






