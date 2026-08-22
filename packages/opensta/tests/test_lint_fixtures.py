import pytest
from tclint.commands.plugins import PluginManager
from tclint.parser import Parser
from tclint.violations import Rule

from tclint_plugins_opensta import SUPPORTED_VERSIONS

VALID = [
    "create_clock -name clk -period 10 {clk1 clk2}",
    "create_clock -period 10",
    "set_input_delay -clock clk 0 {in1 in2}",
    "set_output_delay -clock clk 0.5 -max {out1}",
    "get_cells -hierarchical -filter {full_name =~ foo*} *",
    "group_path -name reg2reg -from [get_clocks clk] -weight 2",
    "set_false_path -from [get_clocks clk1] -to [get_clocks clk2]",
    "all_registers -clock [get_clocks clk]",
    "report_checks -path_delay max -digits 4",
    "define_corners fast slow typical",
]

INVALID = [
    # unrecognized switch
    "create_clock -period 10 -bogus_switch foo",
    # -clock supplied twice, not marked repeated
    "set_input_delay -clock clk -clock clk2 0 {in1}",
    # group_path documents -name without brackets; still shouldn't accept an
    # unknown switch
    "group_path -name reg2reg -not_a_real_switch foo",
    # get_cells: unknown switch
    "get_cells -not_a_real_switch foo *",
]


@pytest.fixture(params=SUPPORTED_VERSIONS)
def commands(request):
    plugins = PluginManager()
    return plugins.get_commands([f"opensta-{request.param}"])


@pytest.mark.parametrize("snippet", VALID)
def test_valid_usage(commands, snippet):
    parser = Parser(commands=commands)
    parser.parse(snippet)
    command_arg_violations = [v for v in parser.violations if v.id == Rule.COMMAND_ARGS]
    assert not command_arg_violations, (
        f"unexpected violation(s) for {snippet!r}: {command_arg_violations}"
    )


@pytest.mark.parametrize("snippet", INVALID)
def test_invalid_usage(commands, snippet):
    parser = Parser(commands=commands)
    parser.parse(snippet)
    command_arg_violations = [v for v in parser.violations if v.id == Rule.COMMAND_ARGS]
    assert command_arg_violations, f"expected a violation for {snippet!r}, got none"
