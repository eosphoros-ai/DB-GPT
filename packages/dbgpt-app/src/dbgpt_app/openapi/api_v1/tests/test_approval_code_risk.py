"""Static code analysis + refined shell read-only classification tests."""

import pytest

from dbgpt_app.openapi.api_v1.approval import POLICY, TIER_AUTO, TIER_CONFIRM
from dbgpt_app.openapi.api_v1.approval_code_risk import analyze_python


def _code(text: str) -> dict:
    return {"code": text}


SAFE_ANALYSIS = """
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv(FILE_PATH)
summary = df.groupby('region')['sales'].sum()
print(summary.describe())
fig, ax = plt.subplots()
summary.plot(ax=ax)
fig.savefig(PLOT_DIR + '/sales.png')
"""


@pytest.mark.parametrize(
    "snippet",
    [
        SAFE_ANALYSIS,
        "import json, math\nprint(math.sqrt(json.loads('[4]')[0]))",
        "import os\nos.makedirs(PLOT_DIR, exist_ok=True)\nprint(os.getcwd())",
        "from collections import Counter\nprint(Counter('aab'))",
        "df = pd.read_csv(FILE_PATH)\nprint(df.to_csv(index=False))",
        "",  # empty payload executes nothing
        # read-only discovery scan (sqlite3 import, no DB writes)
        "import sqlite3, os\nfor r, d, fs in os.walk('/tmp'):\n"
        "    for f in fs:\n        if f.endswith('.db'): print(os.path.join(r, f))",
        "import sqlite3\ncon = sqlite3.connect(FILE_PATH)\n"
        "print(con.execute('SELECT COUNT(*) FROM t').fetchall())",
    ],
)
def test_provably_safe_analysis_code(snippet):
    risk = analyze_python(snippet)
    assert risk.parse_ok
    assert not risk.has_sink
    assert risk.provably_safe
    assert POLICY.classify("code_interpreter", _code(snippet))[0] == TIER_AUTO


@pytest.mark.parametrize(
    "snippet,why",
    [
        ("exec(payload)", "exec"),
        ("import subprocess\nsubprocess.run(['ls'])", "subprocess"),
        ("import requests\nrequests.get('http://x/api')", "network"),
        ("with open('out.csv', 'w') as fh:\n    fh.write('a')", "write open"),
        ("import shutil\nshutil.rmtree('/tmp/x')", "fs delete"),
        ("df.to_csv('/tmp/out.csv')", "path write"),
        ("import pickle\npickle.loads(blob)", "deserialization import"),
        ("import socket\ns = socket.socket()", "socket"),
        ("os.system('rm -rf /tmp/x')", "os.system"),
        ("import urllib.request\nurllib.request.urlopen(u)", "urllib"),
        ("import sqlite3\ncon = sqlite3.connect(p)\n"
         "con.execute('DELETE FROM t')", "sqlite write literal"),
        ("import sqlite3\ncon = sqlite3.connect(p)\n"
         "con.executescript(script)", "executescript"),
    ],
)
def test_sink_code_confirms(snippet, why):
    risk = analyze_python(snippet)
    assert risk.has_sink, why
    assert not risk.provably_safe
    tier, rule_id = POLICY.classify("code_interpreter", _code(snippet))
    assert tier == TIER_CONFIRM
    assert rule_id == "code.static_sink"


@pytest.mark.parametrize(
    "snippet",
    [
        "import mypkg\nprint(mypkg.run())",  # unknown import: not provable
        "def f(:\n    pass",  # unparsable snippet
        # non-literal SQL cannot be proven read-only
        "import sqlite3\ncon = sqlite3.connect(p)\ncon.execute(q)",
    ],
)
def test_unknown_code_falls_to_fail_safe(snippet):
    risk = analyze_python(snippet)
    assert not risk.provably_safe
    assert not risk.has_sink
    tier, rule_id = POLICY.classify("code_interpreter", _code(snippet))
    assert tier == TIER_CONFIRM
    assert rule_id == "failsafe.gated_tool"


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "LC_ALL=C grep -n pattern data.csv",
        "df -h | grep /dev",
        "tar -tf archive.tar",
        "sed -n '1,5p' data.txt",
        "awk '{print $1}' data.txt",
        "find . -name '*.log' | head -5",
        "cut -d, -f1 data.csv | uniq -c | sort -rn",
        "sha256sum data.csv",
    ],
)
def test_shell_readonly_still_auto(command):
    tier, rule_id = POLICY.classify("shell_interpreter", {"command": command})
    assert tier == TIER_AUTO, command
    assert rule_id == "shell.readonly"


@pytest.mark.parametrize(
    "command",
    [
        "ls > out.txt",  # redirection writes a file
        "cat a b >> merged.txt",
        "find . -name '*.tmp' -delete",
        "find . -exec rm {} \\;",
        "sort -o out.txt data.txt",
        "sed -i 's/a/b/' data.txt",
        "awk 'BEGIN{system(\"rm x\")}'",
        "tar -xzf archive.tar",
    ],
)
def test_shell_writers_confirm(command):
    tier, _ = POLICY.classify("shell_interpreter", {"command": command})
    assert tier == TIER_CONFIRM, command


def test_trace_exposes_static_rules():
    verdict, trace = POLICY.classify_trace("code_interpreter", _code(SAFE_ANALYSIS))
    assert verdict == (TIER_AUTO, "code.static_auto")
    hits = [t["rule_id"] for t in trace if t["hit"]]
    assert "code.static_auto" in hits


def test_renamed_tools_classify_same_as_historical_aliases():
    from dbgpt_app.openapi.api_v1.approval import TIER_DENY

    assert POLICY.classify("bash", {"command": "ls"}) == POLICY.classify(
        "shell_interpreter", {"command": "ls"}
    )
    safe = {"code": "import pandas as pd\nprint(pd.read_csv(FILE_PATH))"}
    assert POLICY.classify("code", safe) == (TIER_AUTO, "code.static_auto")
    assert POLICY.classify("bash", {"command": "rm -rf /"})[0] == TIER_DENY
    sink = {"code": "import subprocess\nsubprocess.run(['ls'])"}
    assert POLICY.classify("code", sink)[0] == TIER_CONFIRM
