import sys
import zipfile

from ..autogpt.plugins_util import scan_plugin_file

_PLUGIN_DIR = "Auto-GPT-Demo-Plugin-main/src/demo_plugin"


def test_scan_plugin_file_loads_zipped_plugin(tmp_path):
    zip_path = tmp_path / "Auto-GPT-Demo-Plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zfile:
        zfile.writestr(
            f"{_PLUGIN_DIR}/__init__.py",
            "import abc\n"
            "\n"
            "from .helper import PLUGIN_NAME\n"
            "\n"
            "\n"
            "class DemoPlugin(abc.ABC):\n"
            "    def __init__(self):\n"
            "        self._name = PLUGIN_NAME\n",
        )
        zfile.writestr(f"{_PLUGIN_DIR}/helper.py", 'PLUGIN_NAME = "demo-plugin"\n')

    modules_before = set(sys.modules)
    try:
        plugins = scan_plugin_file(str(zip_path))
    finally:
        for name in set(sys.modules) - modules_before:
            del sys.modules[name]

    assert [type(plugin).__name__ for plugin in plugins] == ["DemoPlugin"]
    assert plugins[0]._name == "demo-plugin"
