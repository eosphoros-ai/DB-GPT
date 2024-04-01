

#dbgpt start controller --port 8008  --daemon
#dbgpt start worker --model_name stella-mrl-large-zh-v3.5-1792d --model_path /datas/liab/embeddings_model/stella-mrl-large-zh-v3.5-1792d --worker_type text2vec  --port 8889 --controller_addr http://172.23.52.25:8008 --daemon
##dbgpt start worker --model_name Qwen1.5-72B-Chat-GPTQ-Int4 --model_path /datas/liab/llm_model/Qwen1.5-72B-Chat-GPTQ-Int4 --worker_type llm  --port 8891 --controller_addr http://172.23.52.25:8008 --daemon
#dbgpt start apiserver --api_keys stella-large-zh-v3-1792d  --controller_addr http://172.23.52.25:8008 --port 8100 --daemon
python dbgpt/app/dbgpt_server.py --port 5000  --remote_embedding
# test code :curl http://172.23.52.25:8100/api/v1/embeddings -H "Authorization: Bearer stella-large-zh-v3-1792d" -H "Content-Type: application/json" -d '{"model": "stella-large-zh-v3-1792d","input": "hello world"}'