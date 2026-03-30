# netset2p2p

[![CI](https://github.com/taggedzi/netset2p2p/actions/workflows/ci.yml/badge.svg)](https://github.com/taggedzi/netset2p2p/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://github.com/taggedzi/netset2p2p)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Coverage](.github/badges/coverage.svg)](https://github.com/taggedzi/netset2p2p/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.0.4-informational.svg)](https://github.com/taggedzi/netset2p2p/releases)
[![SBOM](https://img.shields.io/badge/SBOM-CycloneDX-blue)](https://cyclonedx.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🔄 netset → p2p Converter

`netset2p2p` is a lightweight Python library and CLI tool that converts `.netset` IP blocklists into `.p2p` (PeerGuardian-compatible) format.

---

## 🎯 Why This Exists

Many modern blocklists (such as those from FireHOL) are distributed in `.netset` format, while torrent clients like qBittorrent still expect legacy `.p2p` blocklists.

This tool bridges that gap:

> Convert modern blocklists → into formats your torrent client actually understands.

---

## ✨ Features

- Convert `.netset` → `.p2p` (PeerGuardian format)
- Supports:
  - CIDR ranges (`1.2.3.0/24`)
  - Explicit ranges (`1.2.3.0-1.2.3.255`)
  - Single IPs
- Strips comments (`# ...`) and invalid lines
- CLI + Python library interface
- Clean `src/` layout
- CI, linting, type-checking, and tests included

---

## 📦 Installation

### Local install

```bash
python -m pip install -e .
```

### Install with development tools

```bash
python -m pip install -e .[dev]
```

---

## 🚀 Usage

### CLI

```bash
netset2p2p input.netset -o output.p2p
```

Optional: specify a custom label for generated entries:

```bash
netset2p2p input.netset -o output.p2p --label firehol_level1
```

---

### Python Library

```python
from netset2p2p import convert_netset_text_to_p2p

result = convert_netset_text_to_p2p(
    "# firehol\n10.0.0.0/30\n198.51.100.7\n",
    label="firehol",
)

print(result)
```

**Output:**

```
firehol:10.0.0.0-10.0.0.3
firehol:198.51.100.7-198.51.100.7
```

---

## 🔧 Example Workflow

1. Download a `.netset` blocklist (e.g. FireHOL)
2. Convert it:

   ```bash
   netset2p2p firehol_level1.netset -o firehol_level1.p2p
   ```
3. Import the `.p2p` file into your torrent client (e.g. qBittorrent)

---

## 🧪 Development

Run checks locally:

```bash
ruff check .
mypy src
pytest
```

---

## 📦 Release Process

### Prerequisites

* `gh` authenticated for this repository
* Clean git working tree
* Release notes added under `## [Unreleased]` in `CHANGELOG.md`

### Create a release

```bash
python scripts/release.py --bump patch
```

This will:

* Update version in `pyproject.toml`
* Promote changelog entries into a release section
* Run linting, typing, and tests
* Build `sdist` and wheel
* Generate checksums, SBOM (CycloneDX), and provenance
* Tag and push
* Create a GitHub release with artifacts

---

## ⚠️ Disclaimer

This project is an independent tool and is **not affiliated with, endorsed by, or supported by**:

* FireHOL
* qBittorrent
* PeerGuardian
* Any related projects or organizations

Any references to these tools or formats are for **compatibility and demonstration purposes only**.

---

## 🔐 Security Note

IP blocklists provide **limited protection** and should not be relied upon as a primary security or privacy mechanism.

They are best used as a **supplemental layer** alongside proper network, privacy, and verification practices.

---

## 🤖 AI Tooling Notice

This project was created with the assistance of AI tooling.

---

## 📜 License

MIT. See [LICENSE](LICENSE).
