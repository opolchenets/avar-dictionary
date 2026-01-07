#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

LINE_PATTERN = re.compile(
    r'^\s*"?(\d+)\.\s*(.*?)\s*,\s*"?(\d+)\s*,\s*""(.*)""\s*$'
)

LEADING_INDEX_PATTERN = re.compile(r'^\s*"?\s*\d+\.\s*')

def normalize_text(text: str) -> str:
    text = text.strip()
    text = LEADING_INDEX_PATTERN.sub('', text)
    text = text.strip()
    if text.startswith('"') and text.endswith('"') and len(text) > 1:
        text = text[1:-1]
    return text.strip()

def parse_line(line: str, line_number: int) -> tuple[str, str]:
    line = line.strip().lstrip('\ufeff')
    if not line:
        raise ValueError(f"Line {line_number} is empty")

    match = LINE_PATTERN.match(line)
    if match:
        text = normalize_text(match.group(2))
        translation = match.group(4).strip().replace('""', '"')
        return text, translation

    for row in csv.reader([line]):
        if not row:
            break
        if len(row) >= 2:
            text = normalize_text(row[0])
            if len(row) >= 3 and row[1].strip().isdigit():
                translation = row[-1].strip()
            else:
                translation = row[1].strip()
            translation = translation.strip('"').replace('""', '"')
            return text, translation

    raise ValueError(f"Line {line_number} does not match expected format: {line}")

def build_writer(output_path: Path | None) -> tuple[csv.writer, object]:
    if output_path is None:
        return csv.writer(sys.stdout), sys.stdout
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_obj = output_path.open('w', encoding='utf-8', newline='')
    return csv.writer(file_obj), file_obj

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize legacy phrasebook CSV into "
            "section,text,translation,translit columns."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source CSV file."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Path to write the normalized CSV (defaults to stdout)."
    )
    parser.add_argument(
        "-s",
        "--section",
        default="General",
        help="Section name to assign to each phrase."
    )
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    writer, output_handle = build_writer(args.output)
    try:
        writer.writerow(["section", "text", "translation", "translit"])
        with args.input.open('r', encoding='utf-8', newline='') as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                text, translation = parse_line(stripped, line_number)
                writer.writerow([args.section, text, translation, ""])
    finally:
        if output_handle is not sys.stdout:
            output_handle.close()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
