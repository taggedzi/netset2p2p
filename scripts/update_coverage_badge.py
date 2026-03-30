#!/usr/bin/env python3
"""Generate coverage badge artifacts from a coverage.py XML report."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate coverage badge JSON/SVG files.")
    parser.add_argument(
        "--coverage-xml",
        default="coverage.xml",
        help="Path to coverage XML report (default: coverage.xml)",
    )
    parser.add_argument(
        "--output-dir",
        default=".github/badges",
        help="Output directory for coverage badge files (default: .github/badges)",
    )
    return parser.parse_args()


def color_for_percent(percent: int) -> str:
    if percent >= 90:
        return "brightgreen"
    if percent >= 80:
        return "green"
    if percent >= 70:
        return "yellowgreen"
    if percent >= 60:
        return "yellow"
    return "red"


def build_svg(label: str, message: str, color: str) -> str:
    left_width = 70
    right_width = max(38, 10 + len(message) * 7)
    total_width = left_width + right_width
    aria = f"{label}: {message}"
    font = "Verdana,Geneva,DejaVu Sans,sans-serif"

    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" '
            f'height="20" role="img" aria-label="{aria}">'
        ),
        '<linearGradient id="b" x2="0" y2="100%">',
        '  <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>',
        '  <stop offset="1" stop-opacity=".1"/>',
        "</linearGradient>",
        '<mask id="a">',
        f'  <rect width="{total_width}" height="20" rx="3" fill="#fff"/>',
        "</mask>",
        '<g mask="url(#a)">',
        f'  <rect width="{left_width}" height="20" fill="#555"/>',
        f'  <rect x="{left_width}" width="{right_width}" height="20" fill="{color}"/>',
        f'  <rect width="{total_width}" height="20" fill="url(#b)"/>',
        "</g>",
        (
            '<g fill="#fff" text-anchor="middle" '
            f'font-family="{font}" font-size="11">'
        ),
        f'  <text x="{left_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>',
        f'  <text x="{left_width / 2}" y="14">{label}</text>',
        (
            f'  <text x="{left_width + right_width / 2}" y="15" '
            f'fill="#010101" fill-opacity=".3">{message}</text>'
        ),
        f'  <text x="{left_width + right_width / 2}" y="14">{message}</text>',
        "</g>",
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def read_percent(coverage_xml: Path) -> int:
    root = ET.parse(coverage_xml).getroot()
    line_rate = float(root.attrib.get("line-rate", "0"))
    return round(line_rate * 100)


def main() -> int:
    args = parse_args()
    coverage_xml = Path(args.coverage_xml)
    output_dir = Path(args.output_dir)

    if not coverage_xml.exists():
        raise FileNotFoundError(f"Coverage file not found: {coverage_xml}")

    percent = read_percent(coverage_xml)
    color = color_for_percent(percent)
    label = "coverage"
    message = f"{percent}%"

    output_dir.mkdir(parents=True, exist_ok=True)

    json_payload = {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": color,
    }
    (output_dir / "coverage.json").write_text(
        json.dumps(json_payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    (output_dir / "coverage.svg").write_text(build_svg(label, message, color), encoding="utf-8")
    print(f"Wrote coverage badges to {output_dir} ({message})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
