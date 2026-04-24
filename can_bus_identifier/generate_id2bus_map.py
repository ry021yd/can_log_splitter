from fnmatch import fnmatch
import glob
from pathlib import Path
import sys
import argparse
import re
import json
import pprint

PAT_BO = re.compile(r'^\s*BO_\s+(?P<id>\d+)\s+(?P<msg_name>\w+)\s*:\s*(?P<dlc>\d+)\s+(?P<tx_ecu>\w+)\s*')

def collect_files(patterns):
    """Collect files by glob patterns
    Args:
        patterns: array of glob patterns

    Returns:
        files: list of matching files
    """
    files = []
    for p in patterns:
        matches = sorted(glob.glob(p))
        if matches:
            files.extend(matches)
        else:
            files.append(p)
    return files

def load_labels_from_json(json_file):
    with open(json_file, "r", encoding="utf-8") as fp:
        data = json.load(fp)
        items = data.get("map")
        if not isinstance(items, list):
            raise ValueError("Invalid JSON format: 'map' should be a list")

    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid JSON format: each item in 'map' should be a dict")
        file_pattern = item.get("file_pattern")
        bus_label = item.get("bus_label")
        if not file_pattern or not bus_label:
            raise ValueError("Invalid JSON format: each item should contain 'file_pattern' and 'bus_label'")
        result.append({
            "file_pattern": file_pattern,
            "bus_label": bus_label
        })
    return result

def resolve_bus_label(file, label_map):
    name = Path(file).name
    for item in label_map:
        if fnmatch(name, item["file_pattern"]):
            return item["bus_label"]
    return Path(file).stem

def generate_id2bus_map(file_patterns, label_map_json):
    dbc_files = collect_files(file_patterns)
    id2bus = {}

    for file in dbc_files:
        label_map = load_labels_from_json(label_map_json)
        bus_label = resolve_bus_label(file, label_map)

        with open(file, "r", encoding="utf-8") as fp:
            for line in fp:

                # BO record
                match = PAT_BO.search(line)
                if match:
                    id = f'0x{int(match["id"]) & 0x1FFFFFFF:X}'

                    if id not in id2bus:
                        id2bus[id] = {
                            "id": id,
                            "buses": set()
                        }
                    id2bus[id]["buses"].add(bus_label)

    id2bus_list = []
    for item in id2bus.values():
        id2bus_list.append({
            "id": item["id"],
            "buses": sorted(item["buses"])
        })
    
    id2bus_list = sorted(id2bus_list, key=lambda x: int(x["id"], 16))
    
    root = {}
    root["id_to_buses"] = id2bus_list
    return root

def main():
    # get arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-L", "--label-map", help="JSON file containing file pattern to bus label mapping")
    parser.add_argument("-O", "--output", help="output file")
    parser.add_argument("files", nargs="*", help="DBC files for parse, JSON files for input; glob patterns are also accepted")
    args = parser.parse_args()

    if not args.files:
        parser.print_help()
        return 1
    
    id2bus = generate_id2bus_map(args.files, args.label_map)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(id2bus, fp, ensure_ascii=False, indent=2)
    else:
        pprint.pprint(id2bus)

    return 0

if __name__ == '__main__':
    sys.exit(main())

