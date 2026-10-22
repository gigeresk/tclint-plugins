import importlib
from pathlib import Path

import yaml
from tclint.commands.plugins import PluginManager
from tclint_plugins_opensta import LATEST_VERSION, MANIFEST, SUPPORTED_VERSIONS


def test_manifest_and_versions_agree():
    assert set(SUPPORTED_VERSIONS) == set(MANIFEST)
    assert LATEST_VERSION == SUPPORTED_VERSIONS[-1]


def test_versioned_entry_points_resolve():
    plugins = PluginManager()
    for version in SUPPORTED_VERSIONS:
        commands = plugins.load(f"opensta-{version}")
        assert commands is not None, f"opensta-{version} failed to load"
        assert len(commands) > 0


def test_bare_alias_matches_latest():
    plugins = PluginManager()
    bare = plugins.load("opensta")
    latest = plugins.load(f"opensta-{LATEST_VERSION}")
    assert bare is not None
    assert bare == latest


def test_create_clock_present_in_every_version():
    plugins = PluginManager()
    for version in SUPPORTED_VERSIONS:
        commands = plugins.load(f"opensta-{version}")
        assert "create_clock" in commands


def test_docs_cover_every_scraped_command():
    """Every command has a usage doc, except ones that exist only because a null or
    _replace entry in overrides.yaml adds them (no define_cmd_args to scrape)."""
    overrides = yaml.safe_load(
        (Path(__file__).parents[1] / "generator" / "overrides.yaml").read_text()
    )
    adding = {n for n, patch in overrides.items() if patch is None or patch.get("_replace")}
    for version in SUPPORTED_VERSIONS:
        mod = importlib.import_module(
            f"tclint_plugins_opensta.versions.v{version.replace('.', '_')}"
        )
        assert set(mod.docs) <= set(mod.commands)
        missing = set(mod.commands) - set(mod.docs)
        assert missing <= adding, f"{version}: no docs for {sorted(missing)}"
        assert mod.docs["create_clock"]["usage"].startswith("create_clock ")


def test_merge_overrides_do_not_add_commands_to_older_minors():
    # get_scenes is new in 3.0; its overrides.yaml patch must not leak it into 2.7.
    plugins = PluginManager()
    assert "get_scenes" not in plugins.load("opensta-2.7")
    assert "get_scenes" in plugins.load("opensta-3.0")
