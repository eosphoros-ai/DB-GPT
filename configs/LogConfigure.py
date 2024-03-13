# -*- encoding:utf-8 -*-
'''
@describe: 
@author: li anbang
@Create Date: 2022/9/16 15:44
'''
import os
log_file_abs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'log')
if not os.path.exists(log_file_abs_path):
    os.mkdir(log_file_abs_path)

log_file_path = os.path.join(log_file_abs_path, 'log.log')

logging_config = {
    "version": 1,
    "disable_existing_loggers": "false",
    "formatters": {
        "basic": {
            "class": "logging.Formatter",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "format": "%(asctime)s - %(filename)s - [funcName:%(funcName)s-line:%(lineno)d] - %(levelname)s - %(message)s"
        }
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "basic",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "INFO",
            "formatter": "basic",
            "filename": log_file_path,
            # "maxBytes": 1024,
            "backupCount": 30,
            # "mode": "a",
            'when':'D',
            "encoding": "utf-8"
        }
    },

    "loggers": {},

    "root": {
        "handlers": ["file", 'console'],
        "level": "DEBUG"
    }
}
