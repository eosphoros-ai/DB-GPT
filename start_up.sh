python dbgpt/app/dbgpt_server.py --port 5000  --remote_embedding

#  dbgpt start controller --port 8008
# dbgpt start worker --model_name stella-large-zh-v3-1792d --model_path /datas/liab/embeddings_model/stella-large-zh-v3-1792d --worker_type text2vec  --port 8888 --controller_addr http://172.23.52.25:8008
# dbgpt start apiserver --api_keys stella-large-zh-v3-1792d  --controller_addr http://172.23.52.25:8008
# test code :curl http://172.23.52.25:8100/api/v1/embeddings -H "Authorization: Bearer stella-large-zh-v3-1792d" -H "Content-Type: application/json" -d '{"model": "stella-large-zh-v3-1792d","input": "hello world"}'