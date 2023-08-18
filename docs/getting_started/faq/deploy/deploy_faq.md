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