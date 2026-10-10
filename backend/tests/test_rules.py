"""Tests for the rules loader, matching operators and the reloading engine."""

import os
from pathlib import Path
from typing import Any

import pytest

from brain_agent.brain.rules import RulesEngine, RulesError, YamlRuleSource, load_rules

RULE = """
version: 1
hard_rules:
  - id: {id}
    description: d
    when:
      tool: {tool}
{args}    action: {action}
"""


def _rule(
    rule_id: str = "r1", tool: str = "send_email", action: str = "block", args: str = ""
) -> str:
    return RULE.format(id=rule_id, tool=tool, action=action, args=args)


def _write(directory: Path, name: str, content: str) -> None:
    (directory / name).write_text(content, encoding="utf-8")


def _engine(tmp_path: Path, conditions: dict[str, str], tool: str = "t") -> RulesEngine:
    """Engine with one block rule whose ``args`` are the given YAML flow conditions."""
    args = "      args:\n" + "".join(f"        {k}: {v}\n" for k, v in conditions.items())
    _write(tmp_path, "a.yaml", _rule(tool=tool, args=args))
    return RulesEngine(load_rules(tmp_path))


def _matches(engine: RulesEngine, args: dict[str, Any], tool: str = "t") -> bool:
    return bool(engine.evaluate(tool, args))


# --- loader -------------------------------------------------------------------------------


def test_load_valid_file(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.yaml",
        "version: 1\npersona: Hi\nguidelines:\n  - {id: g, text: Be nice, priority: 3}\n"
        + _rule().split("version: 1\n")[1],
    )

    rules = load_rules(tmp_path)

    assert rules.persona == "Hi"
    assert [(g.id, g.priority) for g in rules.guidelines] == [("g", 3)]
    [rule] = rules.hard_rules
    assert (rule.id, rule.action, rule.risk, rule.message) == ("r1", "block", "high", "d")
    assert len(rules.version_hash) == 64


def test_empty_directory_gives_empty_ruleset(tmp_path: Path) -> None:
    rules = load_rules(tmp_path)
    assert rules.persona is None and not rules.guidelines and not rules.hard_rules


def test_duplicate_ids_across_files_are_an_error(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule("same"))
    _write(tmp_path, "b.yaml", _rule("same"))
    with pytest.raises(RulesError, match=r"Duplicate.*same"):
        load_rules(tmp_path)


def test_invalid_regex_names_file_and_rule(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", _rule("broken", args="      args:\n        to: {matches: '('}\n"))
    with pytest.raises(RulesError, match=r"bad\.yaml.*broken"):
        load_rules(tmp_path)


def test_schema_errors_name_the_file(tmp_path: Path) -> None:
    for content in (_rule(action="explode"), "version: 2\n", "[unclosed"):
        _write(tmp_path, "bad.yaml", content)
        with pytest.raises(RulesError, match=r"bad\.yaml"):
            load_rules(tmp_path)


def test_condition_without_operator_is_an_error(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule(args="      args:\n        to: {}\n"))
    with pytest.raises(RulesError, match="r1"):
        load_rules(tmp_path)


def test_only_one_file_may_define_persona(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", "version: 1\npersona: A\n")
    _write(tmp_path, "b.yaml", "version: 1\npersona: B\n")
    with pytest.raises(RulesError, match="persona"):
        load_rules(tmp_path)


def test_files_merge_in_filename_order(tmp_path: Path) -> None:
    _write(tmp_path, "b.yaml", _rule("second"))
    _write(tmp_path, "a.yaml", _rule("first"))
    assert [r.id for r in load_rules(tmp_path).hard_rules] == ["first", "second"]


def test_version_hash_is_stable_and_tracks_content(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule())
    first = load_rules(tmp_path).version_hash
    assert load_rules(tmp_path).version_hash == first
    _write(tmp_path, "a.yaml", _rule(action="require_approval"))
    assert load_rules(tmp_path).version_hash != first


# --- operators ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("condition", "args", "expected"),
    [
        ("{equals: 5}", {"x": 5}, True),
        ("{equals: 5}", {"x": 6}, False),
        ("{not_equals: 5}", {"x": 6}, True),
        ("{not_equals: 5}", {"x": 5}, False),
        ("{in: [a, b]}", {"x": "a"}, True),
        ("{in: [a, b]}", {"x": "c"}, False),
        ("{not_in: [a, b]}", {"x": "c"}, True),
        ("{not_in: [a, b]}", {"x": "a"}, False),
        ("{matches: '^ab'}", {"x": "abc"}, True),
        ("{matches: '^ab'}", {"x": "cab"}, False),
        ("{not_matches: '^ab'}", {"x": "cab"}, True),
        ("{gt: 10}", {"x": 11}, True),
        ("{gt: 10}", {"x": 10}, False),
        ("{gte: 10}", {"x": 10}, True),
        ("{lt: 10}", {"x": 9}, True),
        ("{lt: 10}", {"x": 10}, False),
        ("{lte: 10}", {"x": 10}, True),
        ("{gt: 10}", {"x": "20000"}, True),
        ("{gt: 10}", {"x": "lots"}, False),
        ("{gt: 10}", {"x": True}, False),
        ("{exists: true}", {"x": None}, True),
        ("{exists: true}", {}, False),
        ("{exists: false}", {}, True),
        ("{exists: false}", {"x": 1}, False),
        ("{gt: 1, lt: 5}", {"x": 3}, True),
        ("{gt: 1, lt: 5}", {"x": 7}, False),
        # A missing argument only satisfies exists:false and negative conditions.
        ("{equals: 5}", {}, False),
        ("{in: [a]}", {}, False),
        ("{matches: a}", {}, False),
        ("{gt: 1}", {}, False),
        ("{not_equals: 5}", {}, True),
        ("{not_in: [a]}", {}, True),
        ("{not_matches: a}", {}, True),
    ],
)
def test_operators(tmp_path: Path, condition: str, args: dict[str, Any], expected: bool) -> None:
    assert _matches(_engine(tmp_path, {"x": condition}), args) is expected


def test_all_arg_conditions_must_hold(tmp_path: Path) -> None:
    engine = _engine(tmp_path, {"x": "{gt: 1}", "y": "{equals: ok}"})
    assert _matches(engine, {"x": 2, "y": "ok"})
    assert not _matches(engine, {"x": 2, "y": "no"})


def test_dotted_paths_reach_nested_values_and_list_indexes(tmp_path: Path) -> None:
    engine = _engine(tmp_path, {"customer.tier": "{equals: gold}"})
    assert _matches(engine, {"customer": {"tier": "gold"}})
    assert not _matches(engine, {"customer": {"tier": "basic"}})
    assert not _matches(engine, {"customer": "gold"})

    indexed = _engine(tmp_path, {"to.1": "{exists: true}"})
    assert _matches(indexed, {"to": ["a", "b"]})
    assert not _matches(indexed, {"to": ["a"]})


def test_list_args_match_when_any_element_satisfies(tmp_path: Path) -> None:
    engine = _engine(tmp_path, {"to": "{not_matches: '@acme[.]com$'}"})
    assert _matches(engine, {"to": ["a@acme.com", "b@gmail.com"]})
    assert not _matches(engine, {"to": ["a@acme.com", "c@acme.com"]})
    assert not _matches(engine, {"to": []})


def test_tool_name_exact_and_glob(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule(tool="crm_*"))
    engine = RulesEngine(load_rules(tmp_path))
    assert engine.evaluate("crm_delete_record", {})
    assert not engine.evaluate("send_email", {})
    assert not engine.evaluate("xcrm_a", {})


# --- reload -------------------------------------------------------------------------------


def test_engine_picks_up_file_changes(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule("one"))
    engine = RulesEngine.from_source(YamlRuleSource(tmp_path))
    before = engine.ruleset.version_hash
    assert [m.rule_id for m in engine.evaluate("send_email", {})] == ["one"]

    _write(tmp_path, "b.yaml", _rule("two", tool="other"))

    assert [m.rule_id for m in engine.evaluate("other", {})] == ["two"]
    assert engine.ruleset.version_hash != before


def test_unchanged_files_are_not_reloaded(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule("one"))
    engine = RulesEngine.from_source(YamlRuleSource(tmp_path))
    ruleset = engine.ruleset
    assert engine.reload() is False
    assert engine.ruleset is ruleset


def test_broken_edit_keeps_last_good_rules_until_fixed(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", _rule("one"))
    engine = RulesEngine.from_source(YamlRuleSource(tmp_path))
    path = tmp_path / "a.yaml"
    stat = path.stat()

    _write(tmp_path, "a.yaml", "version: 1\nhard_rules: [oops")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))

    assert [m.rule_id for m in engine.evaluate("send_email", {})] == ["one"]
    with pytest.raises(RulesError):
        engine.reload(force=True)
