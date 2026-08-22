#!/usr/bin/env python3
"""Generates a tclint static command-spec JSON for one OpenSTA minor version.

Scrapes OpenSTA's Tcl sources for the `define_cmd_args "<cmd>" {usage}` /
`parse_key_args "<cmd>" args keys {...} flags {...}` convention used throughout
the codebase to document and parse command arguments, and emits a JSON file
matching tclint's static plugin schema (see tclint's docs/plugins.md).

This is a best-effort scrape, not a full Tcl parser. Cases it can't infer
correctly (which switches/positionals are actually required, variadic/script/
expression value types, subcommands) are patched via overrides.yaml, applied
after scraping. See packages/opensta/README.md for the maintenance workflow.
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

SOURCE_FILES = [
    "sdc/Sdc.tcl",
    "tcl/CmdUtil.tcl",
    "tcl/Property.tcl",
    "tcl/Sta.tcl",
    "tcl/Util.tcl",
    "search/Search.tcl",
    "liberty/Liberty.tcl",
    "network/Link.tcl",
    "network/Network.tcl",
    "graph/Graph.tcl",
    "power/Power.tcl",
    "parasitics/Parasitics.tcl",
    "sdf/Sdf.tcl",
    "spice/WriteSpice.tcl",
    "dcalc/DelayCalc.tcl",
    "verilog/Verilog.tcl",
]

IDENT = r'[A-Za-z_][\w:]*'


def find_matching_brace(text, open_idx):
    """`text[open_idx]` must be '{'. Returns the index of its matching '}'."""
    assert text[open_idx] == "{"
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced braces starting at {open_idx}")


def extract_usage_strings(text):
    """Returns {cmd_name: usage_string} from `define_cmd_args` calls."""
    usages = {}
    for m in re.finditer(
        rf'define_cmd_args\s+"?({IDENT})"?\s*(\\\s*\n\s*)?\{{', text
    ):
        name = m.group(1)
        open_idx = m.end() - 1
        close_idx = find_matching_brace(text, open_idx)
        usages[name] = text[open_idx + 1 : close_idx]
    return usages


def extract_aliases(text):
    """Returns {alias: target} from `define_cmd_alias "alias" "target"` calls."""
    aliases = {}
    for m in re.finditer(
        r'define_cmd_alias\s+"([^"]+)"\s+"([^"]+)"', text
    ):
        aliases[m.group(1)] = m.group(2)
    return aliases


def extract_proc_body(text, name):
    """Returns the body of `proc <name> {args...} {body}`, or of
    `proc_redirect <name> {body}` (a macro used for report_* etc. that expands
    to `proc <name> { args } { ...redirect wrapper... body }`), or None."""
    m = re.search(rf'(?m)^proc\s+{re.escape(name)}\s*\{{', text)
    if m is not None:
        args_open = m.end() - 1
        args_close = find_matching_brace(text, args_open)
        rest = text[args_close + 1 :]
        body_open_rel = rest.index("{")
        body_open = args_close + 1 + body_open_rel
        body_close = find_matching_brace(text, body_open)
        return text[body_open + 1 : body_close]

    m = re.search(rf'(?m)^proc_redirect\s+{re.escape(name)}\s*\{{', text)
    if m is not None:
        body_open = m.end() - 1
        body_close = find_matching_brace(text, body_open)
        return text[body_open + 1 : body_close]

    return None


def extract_key_args(body, name):
    """Returns (keys, flags) lists scraped from a `parse_key_args` call in `body`."""
    body = body.replace("\\\n", " ")
    m = re.search(
        rf'parse_key_args\s+"?{re.escape(name)}"?\s*,?\s*\w+\s*'
        rf'keys\s*\{{([^}}]*)\}}'
        rf'(?:\s*flags\s*\{{([^}}]*)\}})?',
        body,
        re.DOTALL,
    )
    if m is None:
        return [], []
    keys = m.group(1).replace("\\", " ").split()
    flags = (m.group(2) or "").replace("\\", " ").split()
    return keys, flags


def tokenize_usage(usage):
    """Splits a define_cmd_args usage string into top-level tokens, respecting
    a single level of [...] / {...} grouping. Backslash-newline continuations
    are treated as whitespace."""
    s = usage.replace("\\\n", " ").replace("\n", " ")
    tokens = []
    i, n = 0, len(s)
    while i < n:
        if s[i].isspace():
            i += 1
            continue
        if s[i] in "[{":
            open_ch, close_ch = (s[i], "]") if s[i] == "[" else (s[i], "}")
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if s[j] == open_ch:
                    depth += 1
                elif s[j] == close_ch:
                    depth -= 1
                j += 1
            end = j
            # Absorb a trailing "..." (variadic marker) into the same token.
            if s[end : end + 3] == "...":
                end += 3
            tokens.append(s[i:end])
            i = end
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in "[{":
                j += 1
            if s[j : j + 3] == "...":
                j += 3
            tokens.append(s[i:j])
            i = j
    return tokens


def switch_spec():
    return {"required": False, "repeated": False, "value": {"type": "any"}}


def flag_spec():
    return {"required": False, "repeated": False, "value": None}


def is_switch_word(word):
    return bool(word) and word[0] in "->"


def add_switch_doc(switches, inner):
    """Parses one switch-doc token's inner text (e.g. "-hsc separator", or
    "-from x|-rise_from x|-fall_from x") into `switches`, without overwriting
    anything already present (parse_key_args-derived entries win - see
    build_command_spec)."""
    alts = [a.split() for a in inner.split("|")]
    # A shared trailing metavar (e.g. "-through|-thr|-th through_list") is
    # only written once, on the last alternative - propagate it to the
    # earlier ones so they're recognized as value-taking rather than flags.
    shared_metavar = alts[-1][1] if len(alts[-1]) > 1 else None
    for words in alts:
        if not words or not is_switch_word(words[0]):
            continue
        switch_name = words[0]
        metavar = words[1] if len(words) > 1 else shared_metavar
        if metavar:
            spec = switch_spec()
            spec["metavar"] = metavar
        else:
            spec = flag_spec()
        switches.setdefault(switch_name, spec)


def build_command_spec(name, usage, keys, flags):
    # Fallback switches, derived directly from the usage string's bracket
    # groups. Always computed - not just when parse_key_args scraping found
    # nothing - because some commands document switches that are actually
    # parsed by a shared helper (e.g. report_path's -format/-fields/-digits
    # come from parse_report_path_options, not its own parse_key_args call),
    # so the usage string is sometimes the more complete source. Entries
    # scraped from parse_key_args (below) take precedence on conflicts, since
    # they're ground truth for value-vs-flag.
    switches = {}
    tokens = tokenize_usage(usage)
    positionals = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "|":
            # Bare alternation marker between undocumented required switch
            # groups (e.g. "-liberty x | -liberty_min y -liberty_max z").
            # The plugin schema can't express "one of these groups is
            # required", so we just don't require any of them - permissive
            # by design.
            i += 1
            continue
        variadic = tok.endswith("...")
        core = tok[:-3] if variadic else tok
        optional = core.startswith("[") and core.endswith("]")
        inner = core[1:-1] if optional else core
        if not inner:
            i += 1
            continue
        words = inner.split()
        if is_switch_word(words[0]):
            # A switch doc token (leading "-" or ">", matching tclint's own
            # switch/positional split). If it's bare (undocumented as
            # optional, e.g. "-name group_name" with no brackets), it's still
            # a switch, not a positional - the bare metavar word that follows
            # it belongs to it, not to the command.
            add_switch_doc(switches, inner)
            if not optional and len(words) == 1 and i + 1 < len(tokens):
                nxt = tokens[i + 1]
                if not (nxt.startswith("[") or is_switch_word(nxt) or nxt == "|"):
                    i += 1  # skip the bare metavar word that follows
            i += 1
            continue
        positionals.append(
            {
                "name": inner,
                "required": not optional,
                "value": {"type": "variadic" if variadic else "any"},
            }
        )
        i += 1

    for k in keys:
        switches[k] = switch_spec()
    for f in flags:
        switches[f] = flag_spec()

    return {"switches": switches, "positionals": positionals}


def deep_merge(base, patch):
    if isinstance(patch, dict) and isinstance(base, dict):
        result = dict(base)
        for k, v in patch.items():
            result[k] = deep_merge(base.get(k), v)
        return result
    return patch


def load_overrides(path):
    if yaml is None:
        raise RuntimeError("pyyaml is required to apply overrides (pip install pyyaml)")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def generate(repo, source_files=SOURCE_FILES):
    """Returns a dict of command name -> spec (or None), for every command
    documented via `define_cmd_args` across `source_files`."""
    commands = {}
    for rel in source_files:
        path = repo / rel
        if not path.exists():
            print(f"warning: {rel} not found in {repo}, skipping", file=sys.stderr)
            continue
        text = path.read_text()
        usages = extract_usage_strings(text)
        for name, usage in usages.items():
            body = extract_proc_body(text, name)
            keys, flags = extract_key_args(body, name) if body is not None else ([], [])
            commands[name] = build_command_spec(name, usage, keys, flags)
        for alias, target in extract_aliases(text).items():
            if target in usages:
                commands[alias] = commands[target]
    return commands


def apply_overrides(commands, overrides):
    for name, patch in overrides.items():
        if patch is None:
            commands[name] = None
        elif patch.get("_replace"):
            commands[name] = {k: v for k, v in patch.items() if k != "_replace"}
        else:
            commands[name] = deep_merge(commands.get(name, {}), patch)
    return commands


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, type=Path, help="path to an OpenSTA checkout")
    ap.add_argument("--out", required=True, type=Path, help="output JSON path")
    ap.add_argument(
        "--overrides",
        type=Path,
        default=Path(__file__).parent / "overrides.yaml",
    )
    ap.add_argument("--check", action="store_true", help="diff against --out instead of writing")
    args = ap.parse_args()

    commands = generate(args.repo)
    overrides = load_overrides(args.overrides)
    commands = apply_overrides(commands, overrides)
    new_content = json.dumps(commands, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not args.out.exists():
            print(f"{args.out} does not exist", file=sys.stderr)
            sys.exit(1)
        old_content = args.out.read_text()
        if old_content != new_content:
            print(f"{args.out} is stale, rerun without --check to regenerate", file=sys.stderr)
            sys.exit(1)
        print(f"{args.out} is up to date ({len(commands)} commands)")
    else:
        args.out.write_text(new_content)
        print(f"wrote {args.out} ({len(commands)} commands)")


if __name__ == "__main__":
    main()
