from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .utils import hex_canid_to_int

@dataclass(frozen=True)
class IgnoreIdRule:
    value: int
    mask: int

    def matches(self, can_id: int) -> bool:
        return (can_id & self.mask) == (self.value & self.mask)

@dataclass(frozen=True)
class IdentifierConfig:
    ignore_ids: set[int] = field(default_factory=set)
    ignore_id_rules: list[IgnoreIdRule] = field(default_factory=list)

    def match_ignore_rules(self, can_id: int) -> bool:
        if can_id in self.ignore_ids:
            return True

        return any(rule.matches(can_id) for rule in self.ignore_id_rules)

    @classmethod
    def empty(cls) -> "IdentifierConfig":
        return cls()

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "IdentifierConfig":
        ids = data.get("ignore_ids")
        rules = data.get("ignore_id_rules")

        if ids is None:
            ignore_ids: set[int] = set()
        elif not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise ValueError("'ignore_ids' must be a list[str].")
        else:
            ignore_ids = {hex_canid_to_int(x) for x in ids}

        if rules is None:
            ignore_id_rules: list[IgnoreIdRule] = []
        elif not isinstance(rules, list):
            raise ValueError("'ignore_id_rules' must be a list.")
        else:
            ignore_id_rules = [
                IgnoreIdRule.from_json_dict(rule, idx)
                for idx, rule in enumerate(rules, start=1)
            ]

        return cls(
            ignore_ids=ignore_ids,
            ignore_id_rules=ignore_id_rules,
        )

    @classmethod
    def load_json(cls, json_file: str | Path | None) -> "IdentifierConfig":
        if not json_file:
            return cls.empty()

        with Path(json_file).open("r", encoding="utf-8") as fp:
            return cls.from_json_dict(json.load(fp))