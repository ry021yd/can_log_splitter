import argparse
import glob
import os
from pathlib import Path
import shutil
import sys
import tempfile

from asc_split_checker import AscSplitChecker, load_rules_from_json
from file_splitter import FileSplitter, SplitEngine

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

def get_asc_header(input_asc, encoding="utf-8"):
    """Get ASC header lines for each segment file

    Args:
        input_asc: input ASC file path
        encoding: encoding of the files

    Returns:
        header_lines: list of header lines to prepend to each segment file
    """
    header_lines = []
    with Path(input_asc).open("r", encoding=encoding) as f:
        for line in f:
            parts = line.strip().split()
            if parts and parts[0].replace(".", "").isdigit():
                break
            header_lines.append(line)
    
    return header_lines

def split_canasc(input_ascs, rule_json, output_dir, encoding="utf-8"):
    """Split CANASC files according to rules

    Args:
        input_ascs: list of input ASC files to process
        rule_json: JSON file containing rules for splitting
        output_dir: output directory to write results to
        encoding: encoding of the files

    Returns:
        results: list of results for each input file
    """

    output_dir = Path(output_dir)
    rules=load_rules_from_json(rule_json)
    results = []

    for asc in input_ascs:
        if not asc.endswith(".asc"):
            print(f"Skipping non-ASC file: {asc}")
            continue
        output_dir.mkdir(parents=True, exist_ok=True)

        header_lines = get_asc_header(asc, encoding=encoding)

        checker = AscSplitChecker(
            rules=rules
        )
        engine = SplitEngine(
            input_file=asc,
            output_dir=output_dir,
            header_lines=header_lines,
            encoding=encoding,
        )
        splitter = FileSplitter(
            checker=checker,
            engine=engine
        )
        split_result = splitter.split_file(asc)
        results.append(split_result)

    return results

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_files", help="Input files to process; glob patterns are also accepted", nargs="+")
    parser.add_argument("rule_file", help="Rule file to use for judging to split or not")
    parser.add_argument("output_dir", help="Output directory to write results to")
    parser.add_argument("--encoding", help="Encoding of the files (default: utf-8)", default="utf-8")
    args = parser.parse_args()

    input_files = collect_files(args.input_files)
    split_canasc(
        input_ascs=input_files,
        rule_json=args.rule_file,
        output_dir=args.output_dir,
        encoding=args.encoding,
    )

    return 0

if __name__ == "__main__":
    sys.exit(main())