#!/bin/bash
# This script is used for setting up the environment required for DB-GPT on https://www.autodl.com/

# Usage: source /etc/network_turbo && curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/eosphoros-ai/DB-GPT/main/scripts/setup_autodl_env.sh | bash

# autodl usage: 
# conda activate dbgpt
# cd /root/DB-GPT
# bash scripts/examples/load_examples.sh
# dbgpt start webserver --port 6006

DEFAULT_PROXY="true"
USE_PROXY=$DEFAULT_PROXY

initialize_conda() {
    conda init bash
    eval "$(conda shell.bash hook)"
    source ~/.bashrc
    if [[ $USE_PROXY == "true" ]]; then 
        source /etc/network_turbo
        # unset http_proxy && unset https_proxy
    fi
}

setup_conda_environment() {
    conda create -n dbgpt python=3.10 -y
    conda activate dbgpt
}

install_sys_packages() {
    apt-get update -y && apt-get install git-lfs -y
}

clone_repositories() {
    cd /root && git clone https://github.com/eosphoros-ai/DB-GPT.git
    mkdir -p /root/DB-GPT/models && cd /root/DB-GPT/models
    git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
    git clone https://huggingface.co/THUDM/chatglm2-6b
    rm -rf /root/DB-GPT/models/text2vec-large-chinese/.git
    rm -rf /root/DB-GPT/models/chatglm2-6b/.git
}

install_dbgpt_packages() {
    conda activate dbgpt && cd /root/DB-GPT && pip install -e ".[default]"
    cp .env.template .env && sed -i 's/LLM_MODEL=vicuna-13b-v1.5/LLM_MODEL=chatglm2-6b/' .env
}

clean_up() {
    rm -rf `pip cache dir`
    apt-get clean
    rm -f ~/.bash_history
    history -c
}

clean_local_data() {
    rm -rf /root/DB-GPT/pilot/data
    rm -rf /root/DB-GPT/pilot/message
    rm -f /root/DB-GPT/logs/*
    rm -f /root/DB-GPT/logsDbChatOutputParser.log
}

usage() {
    echo "USAGE: $0 [--use-proxy]"
    echo "  [--use-proxy] Use proxy settings (Optional)"
    echo "  [-h|--help] Usage message"
}

# Command line arguments parsing
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --use-proxy)
        USE_PROXY="true"
        shift
        ;;
        -h|--help)
        help="true"
        shift
        ;;
        *)
        usage
        exit 1
        ;;
    esac
done

if [[ $help ]]; then
    usage
    exit 0
fi

# Main execution

if [[ $USE_PROXY == "true" ]]; then
    echo "Using proxy settings..."
    source /etc/network_turbo
fi

initialize_conda
setup_conda_environment
install_sys_packages
clone_repositories
install_dbgpt_packages
clean_up
