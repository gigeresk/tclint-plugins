import json
from pathlib import Path

_DATA = Path(__file__).parent / "data"

#: OpenSTA major.minor -> {sta_version, commit_sha, generated_at, source_files}
MANIFEST = json.loads((_DATA / "manifest.json").read_text())

#: Supported minors, oldest first (e.g. ["2.7", "3.0", "3.1"]).
SUPPORTED_VERSIONS = sorted(
    MANIFEST, key=lambda v: tuple(int(p) for p in v.split("."))
)

#: The minor the bare "opensta" entry point aliases to.
LATEST_VERSION = SUPPORTED_VERSIONS[-1]
