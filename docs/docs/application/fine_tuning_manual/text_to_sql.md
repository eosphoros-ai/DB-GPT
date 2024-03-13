# Text2SQL Fine-Tuning
We have split the Text2SQL-related fine-tuning code into the `DB-GPT-Hub `sub-project, and you can also view the source code directly.

## Fine-tune pipline

Text2SQL pipline mainly includes the following processes:
- [Build environment](#build-environment)
- [Data processing](#data-processing)
- [Model train](#model-train)
- [Model merge](#model-merge)
- [Model predict](#model-predict)
- [Model evaluation](#model-evaluation)


## Build environment
We recommend using the conda virtual environment to build a Text2SQL fine-tuning environment

```python
git clone https://github.com/eosphoros-ai/DB-GPT-Hub.git
cd DB-GPT-Hub
conda create -n dbgpt_hub python=3.10 
conda activate dbgpt_hub
conda install -c conda-forge poetry>=1.4.0
poetry install
```

The current project supports multiple LLMs and can be downloaded on demand. In this tutorial, we use `CodeLlama-13b-Instruct-hf` as the base model. The model can be downloaded from platforms such as [HuggingFace](https://huggingface.co/) and [Modelscope](https://modelscope.cn/models). Taking HuggingFace as an example, the download command is:
```python
cd Your_model_dir
git lfs install
git clone git@hf.co:codellama/CodeLlama-13b-Instruct-hf
```

## Data processing

### Data collection
The case data of this tutorial mainly uses the `Spider` dataset as an example:
- introduction:  the `Spider` dataset is recognized as the most difficult large-scale cross-domain evaluation list in the industry. It contains 10,181 natural language questions and 5,693 SQL statements, involving more than 200 databases in 138 different fields.
- download: [download](https://drive.google.com/uc?export=download&id=1TqleXec_OykOYFREKKtschzY29dUcVAQ) the data set to the project directory, which is located in `dbgpt_hub/data/spider`.

### Data processing
The project uses the information matching generation method for data preparation, that is, the `SQL + Repository` generation method that combines table information. This method combines the data table information to better understand the structure and relationship of the data table, and to better generate SQL that meets the needs.

The project has encapsulated the relevant processing code in the corresponding script. You can directly run the script command with one click. The generated training sets `example_text2sql_train.json` and `example_text2sql_dev.json` will be obtained in the `dbgpt_hub/data/` directory.

```python
# Generate train data and dev(eval) data
sh dbgpt_hub/scripts/gen_train_eval_data.sh
```
There are `8659` items in the training set and `1034` items in the dev set. The generated training set data format is as follows:
```json
{
  "db_id": "department_management",
  "instruction": "I want you to act as a SQL terminal in front of an example database, you need only to return the sql command to me.Below is an instruction that describes a task, Write a response that appropriately completes the request.\n\"\n##Instruction:\ndepartment_management contains tables such as department, head, management. Table department has columns such as Department_ID, Name, Creation, Ranking, Budget_in_Billions, Num_Employees. Department_ID is the primary key.\nTable head has columns such as head_ID, name, born_state, age. head_ID is the primary key.\nTable management has columns such as department_ID, head_ID, temporary_acting. department_ID is the primary key.\nThe head_ID of management is the foreign key of head_ID of head.\nThe department_ID of management is the foreign key of Department_ID of department.\n\n",
  "input": "###Input:\nHow many heads of the departments are older than 56 ?\n\n###Response:",
  "output": "SELECT count(*) FROM head WHERE age  >  56",
  "history": []
}
```

Configure the training data file in `dbgpt_hub/data/dataset_info.json`. The value of the corresponding key in the json file defaults to `example_text2sql`. This value is the value that needs to be passed in for the parameter `--dataset` in the subsequent training script train_sft. The `file_name` in json The value is the file name of the training set.


### Code interpretation
The core code of data processing is mainly in `dbgpt_hub/data_process/sql_data_process.py`. The core processing class is `ProcessSqlData()`, and the core processing function is `decode_json_file()`.

`decode_json_file()` first processes the table information in the `Spider` data into a dictionary format. The `key` and `value` are respectively the `db_id` and the `table` and `column` information corresponding to the `db_id` into the required format, for example:
```json
{
  "department_management": department_management contains tables such as department, head, management. Table department has columns such as Department_ID, Name, Creation, Ranking, Budget_in_Billions, Num_Employees. Department_ID is the primary key.\nTable head has columns such as head_ID, name, born_state, age. head_ID is the primary key.\nTable management has columns such as department_ID, head_ID, temporary_acting. department_ID is the primary key.\nThe head_ID of management is the foreign key of head_ID of head.\nThe department_ID of management is the foreign key of Department_ID of department.
}
```
Then fill the `{}` part of `INSTRUCTION_PROMPT` in the config file with the above text to form the final instruction. `INSTRUCTION_PROMPT` is as follows:
```json
INSTRUCTION_PROMPT = "I want you to act as a SQL terminal in front of an example database, you need only to return the sql command to me.Below is an instruction that describes a task, Write a response that appropriately completes the request.\n ##Instruction:\n{}\n"
```

Finally, the question and query corresponding to each `db_id`in the training set and validation set are processed into the format required for model SFT training, that is, the data format shown in the execution part of the data processing code above.


:::info note
If you want to collect more data for training yourself, you can use the relevant code of this project to process it according to the above logic.
:::


## Model train
For the sake of simplicity, this reproduction tutorial uses LoRA fine-tuning to run directly as an example, but project fine-tuning can support not only `LoRA` but also `QLoRA` and [deepspeed](https://github.com/microsoft/DeepSpeed) acceleration. The detailed parameters of the training script `dbgpt_hub/scripts/train_sft.sh` are as follows:

```json
CUDA_VISIBLE_DEVICES=0 python dbgpt_hub/train/sft_train.py \
    --model_name_or_path Your_download_CodeLlama-13b-Instruct-hf_path \
    --do_train \
    --dataset example_text2sql_train \
    --max_source_length 2048 \
    --max_target_length 512 \
    --finetuning_type lora \
    --lora_target q_proj,v_proj \
    --template llama2 \
    --lora_rank 64 \
    --lora_alpha 32 \
    --output_dir dbgpt_hub/output/adapter/code_llama-13b-2048_epoch8_lora \
    --overwrite_cache \
    --overwrite_output_dir \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 16 \
    --lr_scheduler_type cosine_with_restarts \
    --logging_steps 50 \
    --save_steps 2000 \
    --learning_rate 2e-4 \
    --num_train_epochs 8 \
    --plot_loss \
    --bf16
```

Introduction to key parameters and meanings in train_sft.sh:
- `model_name_or_path` : Path to the LLM model used.
- `dataset`: The value is the configuration name of the training data set, corresponding to the outer key value in `dbgpt_hub/data/dataset_info.json`, such as `example_text2sql`.
- `max_source_length`: Enter the text length of the model. The effect parameter of this tutorial is `2048`, which is the optimal length after multiple experiments and analysis.
- `max_target_length`: The sql content length of the output model, set to `512`.
- `template`: The lora part of different model fine-tuning in the project settings. For the Llama2 series models, it is set to `llama2`.
- `lora_target`: The network parameter changing part during LoRA fine-tuning.
- `finetuning_type`: Finetuning type, the value is `[ptuning, lora, freeze, full]`, etc.
- `lora_rank`: Rank size in LoRA fine-tuning.
- `lora_alpha`: scaling factor in LoRA fine-tuning.
- `output_dir`: The path output by the Peft module during SFT fine-tuning. The default setting is under the `dbgpt_hub/output/adapter/` path.
- `per_device_train_batch_size`: The batch of training samples on each GPU. If the computing resources support it, it can be set to larger. The default is `1`.
- `gradient_accumulation_steps`: The accumulated steps value of gradient update.
- `lr_scheduler_type`: learning rate type.
- `logging_steps`: steps interval for log saving.
- `save_steps`: The steps size value of ckpt saved by the model.
- `num_train_epochs`: The number of epochs of training data.
- `learning_rate`: learning rate, the recommended learning rate is `2e-4`.

If you want to train based on `QLoRA`, you can add the parameter quantization_bit to the script to indicate whether to quantize. The value is `[4 or 8]` to enable quantization.
If you want to fine-tune different LLMs, the key parameters `lora_target` and `template` corresponding to different models can be changed by referring to the relevant content in the project's `README.md`.

## Model merge


## Model predict
After the model training is completed, to predict the trained model, you can directly run `predict_sft.sh` in the project script directory.

Prediction run command:
```python
sh ./dbgpt_hub/scripts/predict_sft.sh
```

In the project directory `./dbgpt_hub/output/pred/`, this file path is the location of the default output of the model prediction results (if it does not exist, it needs to be created). The detailed parameters in `predict_sft.sh` for this tutorial are as follows:
```python

echo " predict Start time: $(date)"
## predict
CUDA_VISIBLE_DEVICES=0 python dbgpt_hub/predict/predict.py \
    --model_name_or_path Your_download_CodeLlama-13b-Instruct-hf_path \
    --template llama2 \
    --finetuning_type lora \
    --checkpoint_dir Your_last_peft_checkpoint-4000  \
    --predicted_out_filename Your_model_pred.sql

echo "predict End time: $(date)"
```
The value of the parameter `--predicted_out_filename` is the file name of the result predicted by the model, and the results can be found in the `dbgpt_hub/output/pred` directory.


## Model evaluation
For the evaluation of the model's effect on the dataset, the default is on the `Spider` dataset. Run the following command:

```python
python dbgpt_hub/eval/evaluation.py --plug_value --input  Your_model_pred.sql
```

The results generated by large models have a certain degree of randomness because they are closely related to parameters such as `temperature` (can be adjusted in `GeneratingArguments` in `/dbgpt_hub/configs/model_args.py`). By default, the execution accuracy of our multiple evaluations is `0.789` and above. We have placed some of the experimental and evaluation results in the project `docs/eval_llm_result.md` for reference only.


`DB-GPT-Hub` uses `LoRA` to fine-tune the weight file on `Spider`'s training set based on the LLM of `CodeLlama-13b-Instruct-hf`. The weight file has been released. Currently, it has achieved an execution accuracy of about `0.789` on the `Spider`'s evaluation set. The weight file `CodeLlama-13b-sql-lora` is available on [HuggingFace](https://huggingface.co/eosphoros).


## Appendix
The experimental environment of this article is based on a graphics card server with `A100 (40G)`, and the total training time is about 12 hours. If your machine resources are insufficient, you can give priority to reducing the value of the parameter `gradient_accumulation_steps`. In addition, you can consider using `QLoRA` to fine-tune (add `--quantization_bit 4` to the training script `dbgpt_hub/scripts/train_sft.sh`). From our experience, `QLoRA` At `8` epochs, the results are not much different from the `LoRA` fine-tuning results.

# test


The output is as follows:


```python
dbgpt trace --help
```

:::info note

:::
