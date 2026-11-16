# code_interpreter

## Overview

`code_interpreter` executes arbitrary Python code and returns stdout / stderr plus generated artifacts.

It is the main tool for data analysis, calculations, dataframe operations, and chart generation.

## Parameters

```json
{
  "code": "python code string"
}
```

## What it does

- runs Python code in a subprocess
- provides common analysis packages such as `pandas` and `numpy`
- captures text output and generated images
- keeps generated image references available for later HTML rendering

## When to use it

- CSV / Excel / dataframe analysis
- metrics computation
- chart generation
- Python-based preprocessing and transformation

## Example

```python
import pandas as pd

df = pd.read_csv(FILE_PATH)
print(df.head())
print(df.describe())
```

## Notes

- each call is independent
- variables do not persist between calls
- always load the data you need inside the same call
- use `print()` if you want the result to appear in the tool output
- do not use it as the final HTML delivery step
