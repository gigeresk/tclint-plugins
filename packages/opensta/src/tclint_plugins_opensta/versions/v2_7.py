import json
from pathlib import Path

_DATA = Path(__file__).parents[1] / "data"

commands = json.loads((_DATA / "2.7.json").read_text())


def __getattr__(name):
    # Usage docs for tclint-mcp, loaded lazily so plain tclint never reads them.
    if name == "docs":
        return json.loads((_DATA / "docs" / "2.7.json").read_text())
    raise AttributeError(name)
