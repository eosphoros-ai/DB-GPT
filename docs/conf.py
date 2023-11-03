# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import toml
import os
import sys

project = "DB-GPT"
copyright = "2023, csunny"
author = "csunny"

version = "👏👏 0.4.1"
html_title = project + " " + version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autodoc.typehints",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    # "sphinxcontrib.autodoc_pydantic",
    "myst_nb",
    "sphinx_copybutton",
    "sphinx_panels",
    "sphinx_tabs.tabs",
    "IPython.sphinxext.ipython_console_highlighting",
    "sphinx.ext.autosectionlabel",
]
source_suffix = [".ipynb", ".html", ".md", ".rst"]


myst_enable_extensions = [
    "dollarmath",
    "amsmath",
    "deflist",
    "html_admonition",
    "html_image",
    "colon_fence",
    "smartquotes",
    "replacements",
]

# autodoc_pydantic_model_show_json = False
# autodoc_pydantic_field_list_validators = False
# autodoc_pydantic_config_members = False
# autodoc_pydantic_model_show_config_summary = False
# autodoc_pydantic_model_show_validator_members = False
# autodoc_pydantic_model_show_field_summary = False
# autodoc_pydantic_model_members = False
# autodoc_pydantic_model_undoc_members = False

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# multi language config
language = "en"  # ['en', 'zh_CN'] #
locales_dirs = ["./locales/"]
gettext_compact = False
gettext_uuid = True


def setup(app):
    app.add_css_file("css/custom.css")
    app.add_css_file("css/examples.css")
    app.add_css_file("css/termynal.css")
    # app.add_css_file("css/use_cases.css")


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"


html_static_path = ["_static"]
