#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys

from llama_index import GPTVectorStoreIndex, SimpleDirectoryReader

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

# read the document of data dir
documents = SimpleDirectoryReader("data").load_data()
# split the document to chunk, max token size=500, convert chunk to vector

index = GPTVectorStoreIndex(documents)

# save index
index.save_to_disk("index.json")
