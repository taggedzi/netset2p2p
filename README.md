# netset2p2p

[![CI](https://github.com/taggedzi/netset2p2p/actions/workflows/ci.yml/badge.svg)](https://github.com/taggedzi/netset2p2p/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://github.com/taggedzi/netset2p2p)
[![Version](https://img.shields.io/badge/version-1.0.0-informational.svg)](https://github.com/taggedzi/netset2p2p/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`netset2p2p` is a small Python library and CLI tool for converting netset files to p2p files.

## Features

- Converts FireHOL-style `.netset` entries (IP/CIDR) to PeerGuardian `.p2p` ranges
- Handles comment lines starting with `#`
- CLI command: `netset2p2p`
- `src/` package layout for clean packaging
- Tests, linting, and type-checking configuration
- GitHub Actions CI workflow

## Installation

### Local editable install

```bash
python -m pip install -e .
```

### Install with development tools

```bash
python -m pip install -e .[dev]
```

## Usage

### CLI

```bash
netset2p2p input.netset -o output.p2p
```

Use a custom label in generated `.p2p` lines:

```bash
netset2p2p input.netset -o output.p2p --label firehol_level1
```

### Library

```python
from netset2p2p import convert_netset_text_to_p2p

result = convert_netset_text_to_p2p(
    "# firehol\n10.0.0.0/30\n198.51.100.7\n",
    label="firehol",
)
print(result)
```

Example output:

```text
firehol:10.0.0.0-10.0.0.3
firehol:198.51.100.7-198.51.100.7
```

## Development

```bash
ruff check .
mypy src
pytest
```

## Release

Prerequisites:

- `gh` authenticated for `taggedzi/netset2p2p`
- clean git working tree
- release notes added under `## [Unreleased]` in `CHANGELOG.md`

Create a release with a patch bump:

```bash
python scripts/release.py --bump patch
```

The script updates the version in `pyproject.toml` (single source of truth),
promotes changelog entries into a dated release section, runs checks, builds
`sdist`/wheel, generates checksums, creates CycloneDX SBOM and provenance files,
tags/pushes, and creates a GitHub release with attached artifacts.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This project is an independent tool and is not affiliated with, endorsed by,
or supported by FireHOL.

Any mention of FireHOL and any FireHOL-style sample `.netset` files in this
repository are only used to demonstrate one possible input format and conversion
workflow.

## AI Tooling Notice

This project was created with the assistance of AI tooling.
