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
import sys,os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from configs import elk_port, elk_name, elk_index, elk_host


es_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '%(levelname)s - %(asctime)s - process: %(process)d - %(filename)s - %(name)s - %(lineno)d - %(module)s - %(message)s' # 格式字段并未起作用
            }
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'simple'
            },
            'elasticsearch': {
                'level': 'INFO',
                'class': 'cmreslogging.handlers.CMRESHandler',
                'hosts': [{'host': elk_host, 'port': elk_port}],
                'es_index_name': elk_index,
                'es_additional_fields': {'logTime': datetime.datetime.now()},
                'auth_type':  CMRESHandler.AuthType.NO_AUTH,
                # 'flush_frequency_in_sec': 10,
                'use_ssl': False,
                'formatter': 'simple'
            }
        },
        'loggers': {
            'log': {
                'handlers': ['console', 'elasticsearch'],
                'level': 'INFO',
                'propagate': True,
                'disable_existing_loggers': False,
                'formatter': 'simple'
            }
        },
    }


if __name__ == '__main__':
    logging.config.dictConfig(es_config)
    logger = logging.getLogger(elk_name)
    # 使用log模块
    logger.error('test9')
    # 使用log模块
    logger.error('errorer5rorerror')
    logger.info('INFOINFOINFcxcxcdataanalyzeOINFO')

