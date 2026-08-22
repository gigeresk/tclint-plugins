import json
from pathlib import Path

commands = json.loads((Path(__file__).parents[1] / "data" / "3.1.json").read_text())
