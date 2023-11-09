.. _installation:

Installation From Source
==============

To get started, install DB-GPT with the following steps.


1.Preparation
-----------------
**Download DB-GPT**

.. code-block:: shell

    git clone https://github.com/eosphoros-ai/DB-GPT.git

**Install Miniconda**

We use Sqlite as default database, so there is no need for database installation.  If you choose to connect to other databases, you can follow our tutorial for installation and configuration.
For the entire installation process of DB-GPT, we use the miniconda3 virtual environment. Create a virtual environment and install the Python dependencies.
`How to install Miniconda <https://docs.conda.io/en/latest/miniconda.html>`_

.. code-block:: shell

    python>=3.10
    conda create -n dbgpt_env python=3.10
    conda activate dbgpt_env
    # it will take some minutes
    pip install -e ".[default]"

.. code-block:: shell

    cp .env.template .env

2.Deploy LLM Service
-----------------
DB-GPT can be deployed on servers with low hardware requirements or on servers with high hardware requirements.

If you are low hardware requirements you can install DB-GPT by Using third-part LLM REST API Service OpenAI, Azure, tongyi.

.. tip::

        As our project has the ability to achieve OpenAI performance of over 85%,


.. note::

        Notice make sure you have install git-lfs

        centos:yum install git-lfs

        ubuntu:apt-get install git-lfs

        macos:brew install git-lfs

.. tabs::

    .. tab:: OpenAI

        Installing Dependencies

        .. code-block::

          pip install -e ".[openai]"

        Download embedding model

        .. code-block:: shell

            cd DB-GPT
            mkdir models and cd models

            #### embedding model
            git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
            or
            git clone https://huggingface.co/moka-ai/m3e-large

        Configure LLM_MODEL, PROXY_API_URL and API_KEY in `.env` file

        .. code-block:: shell

            LLM_MODEL=chatgpt_proxyllm
            PROXY_API_KEY={your-openai-sk}
            PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions

        .. tip::

            Make sure your .env configuration is not overwritten


    .. tab:: Vicuna
        `Vicuna-v1.5 <https://huggingface.co/lmsys/vicuna-13b-v1.5>`_ based on llama-2 has been released, we recommend you set `LLM_MODEL=vicuna-13b-v1.5` to try this model)

        .. list-table:: vicuna-v1.5 hardware requirements
            :widths: 50 50 50
            :header-rows: 1

            * - Model
              - Quantize
              - VRAM Size
            * - vicuna-7b-v1.5
              - 4-bit
              - 8 GB
            * - vicuna-7b-v1.5
              - 8-bit
              - 12 GB
            * - vicuna-13b-v1.5
              - 4-bit
              - 12 GB
            * - vicuna-13b-v1.5
              - 8-bit
              - 20 GB


        .. code-block:: shell

            cd DB-GPT
            mkdir models and cd models

            #### embedding model
            git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
            or
            git clone https://huggingface.co/moka-ai/m3e-large

            #### llm model, if you use openai or Azure or tongyi llm api service, you don't need to download llm model
            git clone https://huggingface.co/lmsys/vicuna-13b-v1.5

        The model files are large and will take a long time to download.

        **Configure LLM_MODEL in `.env` file**


        .. code-block:: shell

            LLM_MODEL=vicuna-13b-v1.5

    .. tab:: Baichuan

        .. list-table:: Baichuan hardware requirements
            :widths: 50 50 50
            :header-rows: 1

            * - Model
              - Quantize
              - VRAM Size
            * - baichuan-7b
              - 4-bit
              - 8 GB
            * - baichuan-7b
              - 8-bit
              - 12 GB
            * - baichuan-13b
              - 4-bit
              - 12 GB
            * - baichuan-13b
              - 8-bit
              - 20 GB


        .. code-block:: shell

            cd DB-GPT
            mkdir models and cd models

            #### embedding model
            git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
            or
            git clone https://huggingface.co/moka-ai/m3e-large

            #### llm model
            git clone https://huggingface.co/baichuan-inc/Baichuan2-7B-Chat
            or
            git clone https://huggingface.co/baichuan-inc/Baichuan2-13B-Chat

        The model files are large and will take a long time to download.

        **Configure LLM_MODEL in `.env` file**

        please rename Baichuan path to "baichuan2-13b" or "baichuan2-7b"

        .. code-block:: shell

            LLM_MODEL=baichuan2-13b

    .. tab:: ChatGLM


        .. code-block:: shell

            cd DB-GPT
            mkdir models and cd models

            #### embedding model
            git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
            or
            git clone https://huggingface.co/moka-ai/m3e-large

            #### llm model
            git clone https://huggingface.co/THUDM/chatglm2-6b

        The model files are large and will take a long time to download.

        **Configure LLM_MODEL in `.env` file**

        please rename chatglm model path to "chatglm2-6b"

        .. code-block:: shell

            LLM_MODEL=chatglm2-6b

    .. tab:: Other LLM API

        Download embedding model

        .. code-block:: shell

            cd DB-GPT
            mkdir models and cd models

            #### embedding model
            git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
            or
            git clone https://huggingface.co/moka-ai/m3e-large

        Now DB-GPT support LLM REST API TYPE:

        .. note::

            * OpenAI
            * Azure
            * Aliyun tongyi
            * Baidu wenxin
            * Zhipu
            * Baichuan
            * Bard

        Configure LLM_MODEL and PROXY_API_URL and API_KEY in `.env` file

        .. code-block:: shell

            #OpenAI
            LLM_MODEL=chatgpt_proxyllm
            PROXY_API_KEY={your-openai-sk}
            PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions

            #Azure
            LLM_MODEL=chatgpt_proxyllm
            PROXY_API_KEY={your-azure-sk}
            PROXY_API_BASE=https://{your domain}.openai.azure.com/
            PROXY_API_TYPE=azure
            PROXY_SERVER_URL=xxxx
            PROXY_API_VERSION=2023-05-15
            PROXYLLM_BACKEND=gpt-35-turbo

            #Aliyun tongyi
            LLM_MODEL=tongyi_proxyllm
            TONGYI_PROXY_API_KEY={your-tongyi-sk}
            PROXY_SERVER_URL={your_service_url}

            ## Baidu wenxin
            LLM_MODEL=wenxin_proxyllm
            PROXY_SERVER_URL={your_service_url}
            WEN_XIN_MODEL_VERSION={version}
            WEN_XIN_API_KEY={your-wenxin-sk}
            WEN_XIN_SECRET_KEY={your-wenxin-sct}

            ## Zhipu
            LLM_MODEL=zhipu_proxyllm
            PROXY_SERVER_URL={your_service_url}
            ZHIPU_MODEL_VERSION={version}
            ZHIPU_PROXY_API_KEY={your-zhipu-sk}

            ## Baichuan
            LLM_MODEL=bc_proxyllm
            PROXY_SERVER_URL={your_service_url}
            BAICHUN_MODEL_NAME={version}
            BAICHUAN_PROXY_API_KEY={your-baichuan-sk}
            BAICHUAN_PROXY_API_SECRET={your-baichuan-sct}

            ## bard
            LLM_MODEL=bard_proxyllm
            PROXY_SERVER_URL={your_service_url}
            # from https://bard.google.com/     f12-> application-> __Secure-1PSID
            BARD_PROXY_API_KEY={your-bard-token}

        .. tip::

            Make sure your .env configuration is not overwritten

    .. tab:: llama.cpp

        DB-GPT already supports `llama.cpp <https://github.com/ggerganov/llama.cpp>`_ via `llama-cpp-python <https://github.com/abetlen/llama-cpp-python>`_ .

        **Preparing Model Files**

        To use llama.cpp, you need to prepare a gguf format model file, and there are two common ways to obtain it, you can choose either:

        **1. Download a pre-converted model file.**

        Suppose you want to use `Vicuna 13B v1.5 <https://huggingface.co/lmsys/vicuna-13b-v1.5>`_ , you can download the file already converted from `TheBloke/vicuna-13B-v1.5-GGUF <https://huggingface.co/TheBloke/vicuna-13B-v1.5-GGUF>`_ , only one file is needed. Download it to the `models` directory and rename it to `ggml-model-q4_0.gguf`.

        .. code-block::

          wget https://huggingface.co/TheBloke/vicuna-13B-v1.5-GGUF/resolve/main/vicuna-13b-v1.5.Q4_K_M.gguf -O models/ggml-model-q4_0.gguf

        **2. Convert It Yourself**

        You can convert the model file yourself according to the instructions in `llama.cpp#prepare-data--run <https://github.com/ggerganov/llama.cpp#prepare-data--run>`_ , and put the converted file in the models directory and rename it to `ggml-model-q4_0.gguf`.

        **Installing Dependencies**

        llama.cpp is an optional dependency in DB-GPT, and you can manually install it using the following command:

        .. code-block::

            pip install -e ".[llama_cpp]"


        **3.Modifying the Configuration File**

        Next, you can directly modify your `.env` file to enable llama.cpp.

        .. code-block::

            LLM_MODEL=llama-cpp
            llama_cpp_prompt_template=vicuna_v1.1

        Then you can run it according to `Run <https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html#run>`_


        **More Configurations**

        In DB-GPT, the model configuration can be done through  `{model name}_{config key}`.

        .. list-table:: More Configurations
            :widths: 50 50 50
            :header-rows: 1

            * - Environment Variable Key
              - Default
              - Description
            * - llama_cpp_prompt_template
              - None
              - Prompt template name, now support: zero_shot, vicuna_v1.1,alpaca,llama-2,baichuan-chat,internlm-chat, If None, the prompt template is automatically determined from model path。
            * - llama_cpp_model_path
              - None
              - Model path
            * - llama_cpp_n_gpu_layers
              - 1000000000
              - Number of layers to offload to the GPU, Set this to 1000000000 to offload all layers to the GPU. If your GPU VRAM is not enough, you can set a low number, eg: 10
            * - llama_cpp_n_threads
              - None
              - Number of threads to use. If None, the number of threads is automatically determined
            * - llama_cpp_n_batch
              - 512
              - Maximum number of prompt tokens to batch together when calling llama_eval
            * - llama_cpp_n_gqa
              - None
              - Grouped-query attention. Must be 8 for llama-2 70b.
            * - llama_cpp_rms_norm_eps
              - 5e-06
              - 5e-6 is a good value for llama-2 models.
            * - llama_cpp_cache_capacity
              - None
              - Maximum cache capacity. Examples: 2000MiB, 2GiB
            * - llama_cpp_prefer_cpu
              - False
              - If a GPU is available, it will be preferred by default, unless prefer_cpu=False is configured.


    .. tab:: vllm

        vLLM is a fast and easy-to-use library for LLM inference and serving.

        **Running vLLM**

        **1.Installing Dependencies**

        vLLM is an optional dependency in DB-GPT, and you can manually install it using the following command:

        .. code-block::

          pip install -e ".[vllm]"

        **2.Modifying the Configuration File**

        Next, you can directly modify your .env file to enable vllm.

        .. code-block::

            LLM_MODEL=vicuna-13b-v1.5
            MODEL_TYPE=vllm

        You can view the models supported by vLLM `here <https://vllm.readthedocs.io/en/latest/models/supported_models.html#supported-models>`_

        Then you can run it according to `Run <https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html#run>`_





3.Prepare sql example(Optional)
-----------------
**(Optional) load examples into SQLite**

.. code-block:: shell

        bash ./scripts/examples/load_examples.sh


On windows platform:

.. code-block:: shell

        .\scripts\examples\load_examples.bat

4.Run db-gpt server
-----------------

.. code-block:: shell

       python pilot/server/dbgpt_server.py

**Open http://localhost:5000 with your browser to see the product.**

