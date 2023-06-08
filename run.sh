#!/bin/bash

function find_python_command() {
    if command -v python &> /dev/null
    then 
        echo "python"
    elif command -v python3 &> /dev/null
    then
        echo "python3"
    else
        echo "Python not found. Please install python."
        exit 1
    fi
}

PYTHONCMD=$(find_python_command)

nohup PYTHONCMD pilot/server/llmserver.py >> /root/server.log 2>&1 &
while [ `grep -c "Uvicorn running on" /root/server.log` -eq '0' ];do
        sleep 1s;
        echo "wait server running"
done
echo "server running"

PYTHONCMD pilot/server/webserver.py 
