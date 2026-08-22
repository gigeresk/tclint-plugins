# tclint-plugins

Command plugins for [tclint](https://github.com/nmoroze/tclint), packaged and
versioned per EDA tool.

Each tool lives in its own installable package under `packages/<tool>/`, following
the same shape: a scraper/generator that derives a tclint command spec from the
tool's own source, one snapshot per supported tool version (so the plugin doesn't go
stale as the tool's command surface evolves), and a test suite that lints real
scripts with the real, installed `tclint`.

## Packages

- [`packages/opensta`](packages/opensta) - `tclint-plugins-opensta`, covering
  [OpenSTA](https://github.com/The-OpenROAD-Project/OpenSTA)'s Tcl/SDC commands,
  versioned by OpenSTA minor release (`2.7`, `3.0`, `3.1`, ...).

## Adding a new tool's plugin

Copy the shape of `packages/opensta/`: `pyproject.toml` declaring a
`tclint-plugins-<tool>` package with `tclint.plugins` entry points, a
`generator/generate.py` that scrapes the tool's source for its command
documentation convention, `src/tclint_plugins_<tool>/{versions,data}/` holding one
JSON command spec + loader module per supported tool version, and `tests/` that
exercises real tclint against the generated specs.

`tclint` itself is only ever a `test` extra dependency, never a runtime one - none
of these packages should pull in tclint (or the tool being scraped) when installed
normally; both are dev/CI-only.

## CI

- `.github/workflows/ci.yml` runs each package's test suite against a real
  installed `tclint`.
- `.github/workflows/regen-check.yml` (weekly + manual) re-derives each package's
  committed specs from their pinned upstream commits to catch generator drift, and
  flags when upstream has moved past what's currently snapshotted.
