llama.cpp
==================================


DB-GPT already supports [llama.cpp](https://github.com/ggerganov/llama.cpp) via [llama-cpp-python](https://github.com/abetlen/llama-cpp-python).

## Running llama.cpp

### Preparing Model Files

To use llama.cpp, you need to prepare a ggml format model file, and there are two common ways to obtain it, you can choose either:

1. Download a pre-converted model file.

Suppose you want to use [Vicuna 7B v1.5](https://huggingface.co/lmsys/vicuna-7b-v1.5), you can download the file already converted from [TheBloke/vicuna-7B-v1.5-GGML](https://huggingface.co/TheBloke/vicuna-7B-v1.5-GGML), only one file is needed. Download it to the `models` directory and rename it to `ggml-model-q4_0.bin`.

```bash
wget https://huggingface.co/TheBloke/vicuna-7B-v1.5-GGML/resolve/main/vicuna-7b-v1.5.ggmlv3.q4_K_M.bin -O models/ggml-model-q4_0.bin
```

2. Convert It Yourself

You can convert the model file yourself according to the instructions in [llama.cpp#prepare-data--run](https://github.com/ggerganov/llama.cpp#prepare-data--run), and put the converted file in the models directory and rename it to `ggml-model-q4_0.bin`.

### Installing Dependencies

llama.cpp is an optional dependency in DB-GPT, and you can manually install it using the following command:

```bash
pip install -e ".[llama_cpp]"
```

### Modifying the Configuration File

Next, you can directly modify your `.env` file to enable llama.cpp.

```env
LLM_MODEL=llama-cpp
llama_cpp_prompt_template=vicuna_v1.1
```

Then you can run it according to [Run](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html#run).


### More Configurations

In DB-GPT, the model configuration can be done through  `{model name}_{config key}`.

| Environment Variable Key      | default | Prompt Template Name|
|----------|-----------| ----------- |
| llama_cpp_prompt_template | None | Prompt template name, now support: `zero_shot, vicuna_v1.1, llama-2,baichuan-chat`, If None, the prompt template is automatically determined from model path。 |
| llama_cpp_model_path |  None  | Model path |
| llama_cpp_n_gpu_layers | 1000000000 |Number of layers to offload to the GPU, Set this to 1000000000 to offload all layers to the GPU. If your GPU VRAM is not enough, you can set a low number, eg: `10` | 
| llama_cpp_n_threads |  None  | Number of threads to use. If None, the number of threads is automatically determined |
| llama_cpp_n_batch |  512  | Maximum number of prompt tokens to batch together when calling llama_eval |
| llama_cpp_n_gqa | None   | Grouped-query attention. Must be 8 for llama-2 70b.|
| llama_cpp_rms_norm_eps |  5e-06  | 5e-6 is a good value for llama-2 models.|
| llama_cpp_cache_capacity |  None  | Maximum cache capacity. Examples: 2000MiB, 2GiB |
| llama_cpp_prefer_cpu |  False  | If a GPU is available, it will be preferred by default, unless prefer_cpu=False is configured. |

## GPU Acceleration

GPU acceleration is supported by default. If you encounter any issues, you can uninstall the dependent packages with the following command:
```bash
pip uninstall -y llama-cpp-python llama_cpp_python_cuda
```

Then install `llama-cpp-python` according to the instructions in [llama-cpp-python](https://github.com/abetlen/llama-cpp-python/blob/main/README.md).


### Mac Usage

Special attention, if you are using Apple Silicon (M1) Mac, it is highly recommended to install arm64 architecture python support, for example:

```bash
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh
bash Miniforge3-MacOSX-arm64.sh
```

### Windows Usage

The use under the Windows platform has not been rigorously tested and verified, and you are welcome to use it. If you have any problems, you can create an [issue](https://github.com/eosphoros-ai/DB-GPT/issues) or [contact us](https://github.com/eosphoros-ai/DB-GPT/tree/main#contact-information) directly.
