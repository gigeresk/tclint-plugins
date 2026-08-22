# tclint-plugins-opensta

[tclint](https://github.com/nmoroze/tclint) command-spec plugins that teach it
OpenSTA's Tcl/SDC commands (`create_clock`, `set_input_delay`, `group_path`, ...),
so `.sdc`/`.tcl` files that use them lint cleanly instead of tripping
"unrecognized command" and similar warnings.

OpenSTA doesn't cut stable, infrequent releases of its command surface - it evolves
continuously, and a single static spec would go stale. Instead, this package ships
one spec per OpenSTA **minor** version (`major.minor`, e.g. `3.1`, matching what
`sta -version` prints), covering all Tcl commands OpenSTA documents via
`define_cmd_args` across `sdc/`, `search/`, `liberty/`, and related source files.

## Usage

```sh
pip install tclint tclint-plugins-opensta
```

Pick the plugin that matches your OpenSTA version (`sta -version`):

```toml
# tclint.toml
commands = ["opensta-3.0"]   # pin to a specific minor
# or
commands = ["opensta"]       # latest minor this package ships
```

```sh
tclint --commands opensta-3.0 my_design.sdc
```

Currently supported minors: `2.7`, `3.0`, `3.1` (see
`src/tclint_plugins_opensta/data/manifest.json` for the exact OpenSTA commit each
was generated from). Older minors can be added the same way on request - see
below.

## How the specs are generated

`generator/generate.py` scrapes an OpenSTA checkout for its
`define_cmd_args "<cmd>" {usage}` / `parse_key_args ... keys {...} flags {...}`
convention (used throughout `sdc/Sdc.tcl` and friends to document and parse
command arguments) and emits a JSON command spec matching tclint's plugin schema.
It's a best-effort scrape, not a full Tcl parser - `generator/overrides.yaml`
patches the handful of cases it can't infer correctly (see comments there).

To add a new minor once OpenSTA bumps (e.g. `3.2`):

```sh
git clone https://github.com/The-OpenROAD-Project/OpenSTA.git /tmp/opensta
cd /tmp/opensta && git log --first-parent --format='%H' -- CMakeLists.txt
# find the newest commit whose CMakeLists.txt still reads "project(STA VERSION 3.2.*"
python packages/opensta/generator/generate.py \
  --repo /tmp/opensta --out packages/opensta/src/tclint_plugins_opensta/data/3.2.json
```

Then add `versions/v3_2.py`, an entry in `data/manifest.json`, and the matching
`[project.entry-points."tclint.plugins"]` line in `pyproject.toml` (and repoint the
bare `opensta` alias, and `LATEST_VERSION` will follow automatically).

## Known limitations

- Best-effort scrape: a handful of commands parse extra switches manually outside
  `parse_key_args` (e.g. via shared helpers), which the scraper mostly recovers from
  the documented usage string but isn't guaranteed to catch perfectly for future
  commands - `generator/overrides.yaml` is the fix point when a real script trips a
  false positive.
- `set_path_margin` (and a few similar exception-path commands) accept a negative
  numeric value as their last positional (e.g. `set_path_margin -setup -67 ...`).
  tclint treats any bare `-`-prefixed word as a switch attempt, so an unquoted
  negative margin is flagged as an unrecognized switch. Quote it
  (`set_path_margin -setup "-67" ...`) to avoid the false positive, or ignore the
  `command-args` violation on that line.
