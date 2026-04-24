import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import pprint
import sys
from typing import Optional

@dataclass
class BusResolveState:
    bus_number: str
    candidates: set[str] | None = None
    seen_ids: set[str] = field(default_factory=set)
    ignored_ids: set[str] = field(default_factory=set)

@dataclass(frozen=True)
class IgnoreIdRule:
    value: int
    mask: int

def normalize_canid(value: str) -> int:
    value = value.strip()
    return int(value, 16)

def load_id2bus_map(json_file: str | Path) -> dict[int, set[str]]:
    with Path(json_file).open("r", encoding="utf-8") as fp:
        data = json.load(fp)
        items = data.get("id_to_buses")

    if not isinstance(items, list):
        raise ValueError("'id_to_buses' must be a list.")

    result: dict[int, set[str]] = {}
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"id2bus[{idx}] must be a dict.")

        can_id = item.get("id")
        buses = item.get("buses")
        if not isinstance(can_id, str):
            raise ValueError(f"id2bus[{idx}].id must be a string.")
        if not isinstance(buses, list) or not all(isinstance(x, str) for x in buses):
            raise ValueError(f"id2bus[{idx}].buses must be a list[str].")

        result[normalize_canid(can_id)] = set(buses)

    return result

def load_config_json(json_file: str | Path | None) -> tuple[set[int] | None, list[IgnoreIdRule] | None]:
    if not json_file:
        return None, None
    with Path(json_file).open("r", encoding="utf-8") as fp:
        data = json.load(fp)
        ids = data.get("ignore_ids")
        rules = data.get("ignore_id_rules")

        if ids is None:
            return_ids = None
        elif not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise ValueError(f"'ignore_ids' must be a list[str].")
        else:
            return_ids = {normalize_canid(id) for id in ids}

        if rules is None:
            return_rules = None
        else:
            if not isinstance(rules, list):
                raise ValueError("'ignore_id_rules' must be a list.")

            return_rules: list[IgnoreIdRule] = []
            for idx, rule in enumerate(rules, start=1):
                if not isinstance(rule, dict):
                    raise ValueError(f"ignore_id_rules[{idx}] must be a dict.")

                value = rule.get("value")
                mask = rule.get("mask")
                if not isinstance(value, str):
                    raise ValueError(f"ignore_id_rules[{idx}].value must be a string.")
                if not isinstance(mask, str):
                    raise ValueError(f"ignore_id_rules[{idx}].mask must be a string.")

                return_rules.append(
                    IgnoreIdRule(
                        value = normalize_canid(value),
                        mask = normalize_canid(mask),
                    )
                )
        
    return return_ids, return_rules

def parse_asc_frame(line: str) -> Optional[tuple[str, int]]:
    parts = line.strip().split()
    if not parts or len(parts) < 7:
        return None
    
    try:
        # Currently, CANXL frames are not supported
        if parts[1] == "CANFD":
            # CANFD
            bus_number = parts[2]
            canid = parts[4]
        else:
            # Classic CAN
            bus_number = parts[1]
            canid = parts[2]
        return bus_number, normalize_canid(canid)
    except IndexError:
        return None

def is_ignored(can_id: int, ignore_ids: set[int] | None, ignore_id_rules: list[IgnoreIdRule] | None) -> bool:
    if ignore_ids is not None and can_id in ignore_ids:
        return True
    
    if ignore_id_rules is not None:
        for rule in ignore_id_rules:
            mask = rule.mask
            if can_id & mask == rule.value & mask:
                return True
    
    return False
    
def resolve_bus_labels(input_asc: str, id2bus_json: str, config_json: str | None, unique_label: bool, max_frames: int) -> list[dict]:
    id2bus = load_id2bus_map(id2bus_json)
    ignore_ids, ignore_id_rules = load_config_json(config_json)

    states: dict[str, BusResolveState] = {}

    with Path(input_asc).open("r", encoding="utf-8") as fp:
        parsed_line_cnt = 0
        for line in fp:          
            parsed = parse_asc_frame(line)
            if parsed is None:
                continue

            bus_number, can_id = parsed
            parsed_line_cnt += 1

            if parsed_line_cnt > max_frames:
                break
            
            state = states.get(bus_number)

            if is_ignored(can_id, ignore_ids, ignore_id_rules):
                if state is None:
                    states[bus_number] = BusResolveState(
                        bus_number = bus_number,
                        ignored_ids = set([f"0x{can_id:X}"])
                    )
                else:
                    state.ignored_ids.add(f"0x{can_id:X}")
                continue

            mapped_labels = id2bus.get(can_id)
            if mapped_labels is None:
                # Currently, unknown id is skipped.
                continue
                    
            if state is None:
                states[bus_number] = BusResolveState(
                        bus_number = bus_number,
                        candidates = set(mapped_labels),
                        seen_ids = set([f"0x{can_id:X}"])
                    )
                continue
            
            if state.candidates is None:
                state.candidates = set(mapped_labels)
            else:
                state.candidates &= set(mapped_labels)

            state.seen_ids.add(f"0x{can_id:X}")
    
    if unique_label:
        changed = True
        while changed:
            changed = False
            resolved_labels = {
                sorted(state.candidates)[0]
                for state in states.values()
                if state.candidates and len(state.candidates) == 1
            }

            for state in states.values():
                if state.candidates is None or len(state.candidates) <= 1:
                    continue

                before = set(state.candidates)
                after = before - resolved_labels

                if before != after:
                    state.candidates = after
                    changed = True
    
    results: list[dict] = []
    for bus_number in sorted(states.keys(), key=lambda x: int(x)):
        state = states[bus_number]

        labels = []
        if state.candidates is None:
            result = "only ignored ids seen"
        else:
            labels = sorted(state.candidates)
            label_count = len(labels)
            if label_count == 1:
                result = "resolved"
            elif label_count == 0:
                result = "no candidates"
            else:
                result = "multiple candidates"

        results.append(
            {
                "bus_number": bus_number,
                "result": result,
                "labels": labels,
                "seen_ids": sorted(state.seen_ids),
                "ignored_ids": sorted(state.ignored_ids)
            }
        )

    return results

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_asc", help="Input ASC file")
    parser.add_argument("id2bus_json", help="JSON file generated by generate_id2bus_map.py")
    parser.add_argument("-O", "--output", help="output file")
    parser.add_argument("-c", "--config-json", help="Configuration file for adding settings such as ignore IDs")
    parser.add_argument("-u", "--unique-label", action="store_true", help="if true, assume that the bus appears on only one interface")
    parser.add_argument("-m", "--max-frames", type=int, default=10000, help="Maximum number of ASC frames to read")
    args = parser.parse_args()

    asc_busmap = resolve_bus_labels(args.input_asc, args.id2bus_json, args.config_json, args.unique_label, args.max_frames) 

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(asc_busmap, fp, ensure_ascii=False, indent=2)
    else:
        pprint.pprint(asc_busmap)

    return 0

if __name__ == '__main__':
    sys.exit(main())