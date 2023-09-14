import uuid
import os
import duckdb
import sqlite3
from datetime import datetime
from typing import Optional, Type, TypeVar

import sqlalchemy as sa

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate,upgrade
from flask.cli import with_appcontext
import subprocess

from sqlalchemy import create_engine,DateTime, String, func, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from alembic import context, command
from alembic.config import Config

default_db_path = os.path.join(os.getcwd(), "meta_data")

os.makedirs(default_db_path, exist_ok=True)

db_path = default_db_path + "/dbgpt.db"
connection = sqlite3.connect(db_path)
engine = create_engine(f'sqlite:///{db_path}')

Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = Session()

Base = declarative_base(bind=engine)

# Base.metadata.create_all()

# 创建Alembic配置对象

alembic_ini_path = default_db_path + "/alembic.ini"
alembic_cfg = Config(alembic_ini_path)

alembic_cfg.set_main_option('sqlalchemy.url',  str(engine.url))

os.makedirs(default_db_path + "/alembic", exist_ok=True)
alembic_cfg.set_main_option('script_location',  default_db_path + "/alembic")

# 将模型和会话传递给Alembic配置
alembic_cfg.attributes['target_metadata'] = Base.metadata
alembic_cfg.attributes['session'] = session


# # 创建表
# Base.metadata.create_all(engine)
#
# # 删除表
# Base.metadata.drop_all(engine)


# app = Flask(__name__)
# default_db_path = os.path.join(os.getcwd(), "meta_data")
# duckdb_path = os.getenv("DB_DUCKDB_PATH", default_db_path + "/dbgpt.db")
# app.config['SQLALCHEMY_DATABASE_URI'] = f'duckdb://{duckdb_path}'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db = SQLAlchemy(app)
# migrate = Migrate(app, db)
#
# # 设置FLASK_APP环境变量
# import os
# os.environ['FLASK_APP'] = 'server.dbgpt_server.py'
#
# @app.cli.command("db_init")
# @with_appcontext
# def db_init():
#     subprocess.run(["flask", "db", "init"])
#
# @app.cli.command("db_migrate")
# @with_appcontext
# def db_migrate():
#     subprocess.run(["flask", "db", "migrate"])
#
# @app.cli.command("db_upgrade")
# @with_appcontext
# def db_upgrade():
#     subprocess.run(["flask", "db", "upgrade"])
#



def ddl_init_and_upgrade():
    # Base.metadata.create_all(bind=engine)
    # 生成并应用迁移脚本
    # command.upgrade(alembic_cfg, 'head')
    # subprocess.run(["alembic", "revision", "--autogenerate", "-m", "Added account table"])
    with engine.connect() as connection:
        alembic_cfg.attributes['connection'] = connection
        command.revision(alembic_cfg, "test", True)
        command.upgrade(alembic_cfg, "head")
    # alembic_cfg.attributes['connection'] =  engine.connect()
    # command.upgrade(alembic_cfg, 'head')

    # with app.app_context():
    #     db_init()
    #     db_migrate()
    #     db_upgrade()


