from dataclasses import dataclass, field
from pathlib import Path
import re
import json
from typing import Iterable

from .bus_label_map import BusLabelMap
from .utils import collect_files, hex_canid_to_int, int_canid_to_hex

PAT_BO = re.compile(r'^\s*BO_\s+(?P<id>\d+)\s+(?P<msg_name>\w+)\s*:\s*(?P<dlc>\d+)\s+(?P<tx_ecu>\w+)\s*')

@dataclass
class Id2BusMap:
    items: dict[int, set[str]] = field(default_factory=dict)

    def add(self, can_id: int, bus_label: str) -> None:
        self.items.setdefault(can_id, set()).add(bus_label)

    def get_labels(self, can_id: int) -> set[str] | None:
        labels = self.items.get(can_id)
        if labels is None:
            return None
        return set(labels)

    def to_json_dict(self) -> dict:
        return {
            "id_to_buses": [
                {
                    "id": int_canid_to_hex(can_id),
                    "buses": sorted(labels),
                }
                for can_id, labels in sorted(self.items.items())
            ]
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "Id2BusMap":
        items = data.get("id_to_buses")
        if not isinstance(items, list):
            raise ValueError("'id_to_buses' must be a list.")

        result = cls()

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"id2bus[{idx}] must be a dict.")

            can_id = item.get("id")
            buses = item.get("buses")

            if not isinstance(can_id, str):
                raise ValueError(f"id2bus[{idx}].id must be a string.")

            if not isinstance(buses, list) or not all(isinstance(x, str) for x in buses):
                raise ValueError(f"id2bus[{idx}].buses must be a list[str].")

            for bus in buses:
                result.add(hex_canid_to_int(can_id), bus)

        return result

    @classmethod
    def load_json(cls, json_file: str | Path) -> "Id2BusMap":
        with Path(json_file).open("r", encoding="utf-8") as fp:
            return cls.from_json_dict(json.load(fp))

    def save_json(self, json_file: str | Path) -> None:
        with Path(json_file).open("w", encoding="utf-8") as fp:
            json.dump(self.to_json_dict(), fp, ensure_ascii=False, indent=2)

    @classmethod
    def from_dbc_with_label_map(
        cls,
        file_patterns: Iterable[str],
        label_map: "BusLabelMap | None" = None,
    ) -> "Id2BusMap":
        result = cls()

        for file in collect_files(file_patterns):
            bus_label = (
                label_map.resolve(file)
                if label_map is not None
                else Path(file).stem
            )

            with Path(file).open("r", encoding="utf-8") as fp:
                for line in fp:
                    match = PAT_BO.search(line)
                    if not match:
                        continue

                    can_id = int(match["id"]) & 0x1FFFFFFF
                    result.add(can_id, bus_label)

        return result

    @classmethod
    def from_dbc_with_label_map_json(
        cls,
        file_patterns: Iterable[str],
        label_map_json: str,
    ) -> "Id2BusMap":
        label_map = BusLabelMap.load_json(label_map_json)
        return Id2BusMap.from_dbc_with_label_map(file_patterns, label_map)