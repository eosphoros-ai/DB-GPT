Installation FAQ
==================================


##### Q1: execute `pip install -r requirements.txt` error, found some package cannot find correct version.
change the pip source.

```bash
# pypi
$ pip install -r requirements.txt -i https://pypi.python.org/simple
```

or

```bash
# tsinghua
$ pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

or

```bash
# aliyun
$ pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/
```

##### Q2: sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file 

make sure you pull latest code or create directory with mkdir pilot/data

##### Q3: The model keeps getting killed.
your GPU VRAM size is not enough, try replace your hardware or replace other llms.

