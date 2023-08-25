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