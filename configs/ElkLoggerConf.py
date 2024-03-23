# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2023/3/13 9:11
'''
# es环境参数
import datetime
import logging.config
from cmreslogging.handlers import CMRESHandler

class ElkLogger():
    def __init__(self, host, port, es_index_name='ChatGPT', elk_name='IndiaChatGPTService'):
        self.elk_name = elk_name
        self.handler = CMRESHandler(hosts=[{'host': host, 'port': port}], auth_type=CMRESHandler.AuthType.NO_AUTH, es_index_name=es_index_name)

    def logSetUpInstance(self):
        self.log = logging.getLogger(self.elk_name)
        self.log.setLevel(logging.INFO)
        self.log.addHandler(self.handler)



if __name__ == '__main__':
    elk_host = '172.23.8.46'
    elk_port = 9200
    elk_name = 'IndiaChatGPTServer'
    elk_index = 'chatgpt'



    handler = CMRESHandler(hosts=[{'host': elk_host, 'port': elk_port}], auth_type=CMRESHandler.AuthType.NO_AUTH, es_index_name=elk_index)
    log = logging.getLogger(elk_name)
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    log.info("This is the message from logging es advanceddataanalysis")
    log.error("This is the message from error logging es advanceddataanalysis")
