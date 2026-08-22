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
