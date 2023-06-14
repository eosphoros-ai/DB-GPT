# Plugins

The ability of Agent and Plugin is the core of whether large models can be automated. In this project, we natively support the plugin mode, and large models can automatically achieve their goals. At the same time, in order to give full play to the advantages of the community, the plugins used in this project natively support the Auto-GPT plugin ecology, that is, Auto-GPT plugins can directly run in our project.

## Local Plugins

### 1.1 How to write local plugins.

- Local plugins use the Auto-GPT plugin template. A simple example is as follows: first write a plugin file called "sql_executor.py".
```python
import pymysql
import pymysql.cursors

def get_conn():
    return pymysql.connect(
        host="127.0.0.1",
        port=int("2883"),
        user="mock",
        password="mock",
        database="mock",
        charset="utf8mb4",
        ssl_ca=None,
    )

def ob_sql_executor(sql: str):
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
        field_names = tuple(i[0] for i in cursor.description)
        result = list(result)
        result.insert(0, field_names)
        return result
    except pymysql.err.ProgrammingError as e:
        return str(e)
```

Then set the "can_handle_post_prompt" method of the plugin template to True. In the "post_prompt" method, write the prompt information and the mapped plugin function.

```python
"""This is a template for DB-GPT plugins."""
from typing import Any, Dict, List, Optional, Tuple, TypeVar, TypedDict

from auto_gpt_plugin_template import AutoGPTPluginTemplate

PromptGenerator = TypeVar("PromptGenerator")

class Message(TypedDict):
    role: str
    content: str

class DBGPTOceanBase(AutoGPTPluginTemplate):
    """
    This is an DB-GPT plugin to connect OceanBase.
    """

    def __init__(self):
        super().__init__()
        self._name = "DB-GPT-OB-Serverless-Plugin"
        self._version = "0.1.0"
        self._description = "This is an DB-GPT plugin to connect OceanBase."

    def can_handle_post_prompt(self) -> bool:
        return True

    def post_prompt(self, prompt: PromptGenerator) -> PromptGenerator:
        from .sql_executor import ob_sql_executor

        prompt.add_command(
            "ob_sql_executor",
            "Execute SQL in OceanBase Database.",
            {"sql": "<sql>"},
            ob_sql_executor,
        )
        return prompt
    ...

```

### 1.2 How to use local plugins

- Pack your plugin project into `your-plugin.zip` and place it in the `/plugins/` directory of the DB-GPT project. After starting the webserver, you can select and use it in the `Plugin Model` section.


## Public Plugins

### 1.1 How to use public plugins

- By default, after launching the webserver, plugins from the public plugin library `DB-GPT-Plugins` will be automatically loaded. For more details, please refer to [DB-GPT-Plugins](https://github.com/csunny/DB-GPT-Plugins)

### 1.2 Contribute to the DB-GPT-Plugins repository

- Please refer to the plugin development process in the public plugin library, and put the configuration parameters in `.plugin_env`

- We warmly welcome everyone to contribute plugins to the public plugin library!


