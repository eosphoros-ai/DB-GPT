Installation FAQ
==================================


##### Q1: execute `pip install -e .` error, found some package cannot find correct version.
change the pip source.

```bash
# pypi
$ pip install -e . -i https://pypi.python.org/simple
```

or

```bash
# tsinghua
$ pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

or

```bash
# aliyun
$ pip install -e . -i http://mirrors.aliyun.com/pypi/simple/
```

##### Q2: sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file 

make sure you pull latest code or create directory with mkdir pilot/data

##### Q3: The model keeps getting killed.

your GPU VRAM size is not enough, try replace your hardware or replace other llms.

##### Q4: How to access website on the public network

You can try to use gradio's [network](https://github.com/gradio-app/gradio/blob/main/gradio/networking.py) to achieve.
```python
import secrets
from gradio import networking
token=secrets.token_urlsafe(32)
local_port=5000
url = networking.setup_tunnel('0.0.0.0', local_port, token)
print(f'Public url: {url}')
time.sleep(60 * 60 * 24)
```

Open `url` with your browser to see the website.

##### Q5: (Windows) execute `pip install -e .` error

The error log like the following:
``` 
× python setup.py bdist_wheel did not run successfully.
  │ exit code: 1
  ╰─> [11 lines of output]
      running bdist_wheel
      running build
      running build_py
      creating build
      creating build\lib.win-amd64-cpython-310
      creating build\lib.win-amd64-cpython-310\cchardet
      copying src\cchardet\version.py -> build\lib.win-amd64-cpython-310\cchardet
      copying src\cchardet\__init__.py -> build\lib.win-amd64-cpython-310\cchardet
      running build_ext
      building 'cchardet._cchardet' extension
      error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/
      [end of output]
```

Download and install `Microsoft C++ Build Tools` from [visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)



##### Q6: `Torch not compiled with CUDA enabled`

```
2023-08-19 16:24:30 | ERROR | stderr |     raise AssertionError("Torch not compiled with CUDA enabled")
2023-08-19 16:24:30 | ERROR | stderr | AssertionError: Torch not compiled with CUDA enabled
```

1. Install [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit-archive)
2. Reinstall PyTorch [start-locally](https://pytorch.org/get-started/locally/#start-locally) with CUDA support.

##### Q7: ImportError: cannot import name 'PersistentClient' from 'chromadb'.

```commandline
pip install chromadb==0.4.10
```

##### Q8: pydantic.error_wrappers.ValidationError:1 validation error for HuggingFaceEmbeddings.model_kwargs extra not permitted

```commandline
pip install langchain>=0.0.286

##### Q9: In Centos OS, No matching distribution found for setuptools_scm

```commandline
pip install --use-pep517 fschat
```

##### Q9: alembic.util.exc.CommandError: Target database is not up to date.

delete files in `DB-GPT/pilot/meta_data/alembic/versions/` and restart.
```commandline
rm -rf DB-GPT/pilot/meta_data/alembic/versions/*
rm -rf DB-GPT/pilot/meta_data/alembic/dbgpt.db
```

##### Q10: How to store DB-GPT metadata into my database

In version 0.4.0, the metadata module of the DB-GPT application has been refactored. All metadata tables will now be automatically saved in the 'dbgpt' database, based on the database type specified in the `.env` file. If you would like to retain the existing data, it is recommended to use a data migration tool to transfer the database table information to the 'dbgpt' database. Additionally, you can change the default database name 'dbgpt' in your `.env` file.

```commandline
### SQLite database (Current default database)
#LOCAL_DB_PATH=data/default_sqlite.db
#LOCAL_DB_TYPE=sqlite

### Mysql database
LOCAL_DB_TYPE=mysql
LOCAL_DB_USER=root
LOCAL_DB_PASSWORD=aa12345678
LOCAL_DB_HOST=127.0.0.1
LOCAL_DB_PORT=3306
# You can change it to your actual metadata database name
LOCAL_DB_NAME=dbgpt

### This option determines the storage location of conversation records. The default is not configured to the old version of duckdb. It can be optionally db or file (if the value is db, the database configured by LOCAL_DB will be used)
CHAT_HISTORY_STORE_TYPE=db
```

##### Q11: pymysql.err.OperationalError: (1142, "ALTER command denied to user '{you db user}'@'{you db host}' for table '{some table name}'")

In version 0.4.0, DB-GPT use migration tool alembic to migrate metadata. If the database user does not have DDL permissions, this error will be reported. You can solve this problem by importing the metadata information separately.

1. Use a privileged user to execute DDL sql file
```bash
mysql -h127.0.0.1 -uroot -paa12345678 < ./assets/schema/knowledge_management.sql
```

2. Run DB-GPT webserver with `--disable_alembic_upgrade`
```bash
python pilot/server/dbgpt_server.py --disable_alembic_upgrade
```
or 
```bash
dbgpt start webserver --disable_alembic_upgrade
```