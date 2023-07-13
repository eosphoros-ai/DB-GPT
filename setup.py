from typing import List

import setuptools
from setuptools import find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()


def parse_requirements(file_name: str) -> List[str]:
    with open(file_name) as f:
        return [
            require.strip()
            for require in f
            if require.strip() and not require.startswith("#")
        ]


setuptools.setup(
    name="db-gpt",
    packages=find_packages(),
    version="0.3.1",
    author="csunny",
    author_email="cfqcsunny@gmail.com",
    description="DB-GPT is an experimental open-source project that uses localized GPT large models to interact with your data and environment."
    " With this solution, you can be assured that there is no risk of data leakage, and your data is 100% private and secure.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=parse_requirements("requirements.txt"),
    url="https://github.com/csunny/DB-GPT",
    license="https://opensource.org/license/mit/",
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "dbgpt_server=pilot.server:webserver",
        ],
    },
)
