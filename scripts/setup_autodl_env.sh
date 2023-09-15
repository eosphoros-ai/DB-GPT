#!/bin/bash
eval "$(conda shell.bash hook)"

source ~/.bashrc

# source /etc/network_turbo
# unset http_proxy && unset https_proxy
conda create -n dbgpt python=3.10 -y

conda activate dbgpt

apt-get update -y && apt-get install git-lfs -y

cd /root && git clone https://github.com/eosphoros-ai/DB-GPT.git

mkdir -p /root/DB-GPT/models && cd /root/DB-GPT/models

git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
git clone https://huggingface.co/THUDM/chatglm2-6b-int4