#!/usr/bin/env python3
"""Automate project releases for netset2p2p.

This script uses `pyproject.toml` as the single source of truth for the version.
It can bump/set the version, roll changelog notes out of Unreleased, run checks,
build artifacts, generate checksums/SBOM/provenance, and publish a GitHub release.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"
README = PROJECT_ROOT / "README.md"
DIST_DIR = PROJECT_ROOT / "dist"
RELEASE_META_DIR = DIST_DIR / "release"


class ReleaseError(RuntimeError):
    """Raised for release validation/runtime errors."""


@dataclass(frozen=True)
class Artifact:
    name: str
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class Versions:
    current: str
    next: str


def run(
    cmd: list[str], *, dry_run: bool = False, check: bool = True, cwd: Path = PROJECT_ROOT
) -> str:
    print(f"+ {' '.join(cmd)}")
    if dry_run:
        return ""
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise ReleaseError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create and publish a project release.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bump", choices=["major", "minor", "patch"], help="SemVer bump type.")
    group.add_argument("--version", help="Explicit SemVer version (X.Y.Z).")
    parser.add_argument("--skip-checks", action="store_true", help="Skip ruff/mypy/pytest checks.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print actions without mutating git/GitHub."
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow running with a dirty git tree (not recommended).",
    )
    return parser.parse_args()


def read_project_metadata() -> dict:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)


def current_version() -> str:
    data = read_project_metadata()
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise ReleaseError(
            "Unable to read a valid SemVer version from pyproject.toml project.version"
        )
    return version


def bump_version(version: str, bump: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(f"Unsupported bump type: {bump}")


def resolve_versions(args: argparse.Namespace) -> Versions:
    curr = current_version()
    if args.version:
        if not VERSION_RE.match(args.version):
            raise ReleaseError("--version must be a plain SemVer value like 1.2.3")
        nxt = args.version
    else:
        nxt = bump_version(curr, args.bump)

    if curr == nxt:
        raise ReleaseError("Current version and target version are identical; nothing to release.")
    return Versions(current=curr, next=nxt)


def ensure_clean_git_tree(*, allow_dirty: bool, dry_run: bool) -> None:
    status = run(["git", "status", "--porcelain"], dry_run=False, check=False)
    if status and not allow_dirty:
        raise ReleaseError(
            "Git tree is dirty. Commit/stash changes first or rerun with --allow-dirty.\n"
            f"Current status:\n{status}"
        )


def ensure_tooling_available(*, skip_checks: bool, dry_run: bool) -> None:
    if not dry_run and shutil.which("gh") is None:
        raise ReleaseError("GitHub CLI `gh` is required but was not found in PATH.")
    if skip_checks:
        return
    if shutil.which("ruff") is None:
        raise ReleaseError("`ruff` is required but was not found in PATH.")
    if shutil.which("mypy") is None:
        raise ReleaseError("`mypy` is required but was not found in PATH.")
    if shutil.which("pytest") is None:
        raise ReleaseError("`pytest` is required but was not found in PATH.")


def update_pyproject_version(new_version: str, *, dry_run: bool) -> None:
    original = PYPROJECT.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^(version\s*=\s*")([^"]+)(")$',
        rf"\g<1>{new_version}\g<3>",
        original,
        count=1,
    )
    if count != 1:
        raise ReleaseError("Failed to update version in pyproject.toml")
    if not dry_run:
        PYPROJECT.write_text(updated, encoding="utf-8")


def update_readme_badge_version(new_version: str, *, dry_run: bool) -> None:
    original = README.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(https://img\.shields\.io/badge/version-)([^-]+)(-informational\.svg)",
        rf"\g<1>{new_version}\g<3>",
        original,
        count=1,
    )
    if count != 1:
        raise ReleaseError("Failed to update README version badge")
    if not dry_run:
        README.write_text(updated, encoding="utf-8")


def extract_unreleased_body(changelog_text: str) -> tuple[str, int, int]:
    unreleased_match = re.search(r"(?m)^## \[Unreleased\]\s*$", changelog_text)
    if not unreleased_match:
        raise ReleaseError("CHANGELOG.md missing `## [Unreleased]` heading")
    start = unreleased_match.end()
    next_release_match = re.search(r"(?m)^## \[[^\]]+\].*$", changelog_text[start:])
    end = start + next_release_match.start() if next_release_match else len(changelog_text)
    body = changelog_text[start:end]
    return body, start, end


def update_changelog(new_version: str, *, dry_run: bool) -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    body, start, end = extract_unreleased_body(text)
    normalized_body = body.strip("\n")
    if not normalized_body.strip():
        raise ReleaseError(
            "No changelog entries found under [Unreleased]. Add notes before creating a release."
        )

    release_date = dt.date.today().isoformat()
    release_block = f"## [{new_version}] - {release_date}\n\n{normalized_body}\n\n"
    replacement = f"\n\n{release_block}"
    updated = text[:start] + replacement + text[end:]

    if not dry_run:
        CHANGELOG.write_text(updated, encoding="utf-8")

    return normalized_body


def run_quality_checks(*, skip_checks: bool, dry_run: bool) -> None:
    if skip_checks:
        print("Skipping quality checks (--skip-checks)")
        return
    run(["ruff", "check", "."], dry_run=dry_run)
    run(["mypy", "src"], dry_run=dry_run)
    run(["pytest"], dry_run=dry_run)


def ensure_build_module(*, dry_run: bool) -> None:
    if dry_run:
        return
    try:
        __import__("build")
    except ModuleNotFoundError as exc:
        raise ReleaseError(
            "Python package `build` is required. Install it with: python -m pip install build"
        ) from exc


def build_artifacts(*, dry_run: bool) -> list[Path]:
    if DIST_DIR.exists() and not dry_run:
        shutil.rmtree(DIST_DIR)
    if not dry_run:
        DIST_DIR.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "build", "--sdist", "--wheel"], dry_run=dry_run)
    if dry_run:
        return [
            DIST_DIR / "netset2p2p-X.Y.Z.tar.gz",
            DIST_DIR / "netset2p2p-X.Y.Z-py3-none-any.whl",
        ]
    artifacts = sorted([p for p in DIST_DIR.iterdir() if p.is_file()])
    if not artifacts:
        raise ReleaseError("No build artifacts were produced in dist/")
    return artifacts


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_artifacts(paths: Iterable[Path]) -> list[Artifact]:
    items: list[Artifact] = []
    for path in paths:
        items.append(
            Artifact(
                name=path.name,
                path=path,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return items


def write_sha256sums(artifacts: list[Artifact], *, dry_run: bool) -> Path:
    output = DIST_DIR / "SHA256SUMS"
    lines = [f"{a.sha256}  {a.name}" for a in artifacts]
    if not dry_run:
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def build_purl(name: str, version: str) -> str:
    return f"pkg:pypi/{name}@{version}"


def write_sbom(project_name: str, version: str, dependencies: list[str], *, dry_run: bool) -> Path:
    if not dry_run:
        RELEASE_META_DIR.mkdir(parents=True, exist_ok=True)
    output = RELEASE_META_DIR / f"{project_name}-{version}.sbom.cdx.json"
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "component": {
                "type": "library",
                "name": project_name,
                "version": version,
                "purl": build_purl(project_name, version),
            },
            "tools": [
                {
                    "vendor": "local",
                    "name": "scripts/release.py",
                }
            ],
        },
        "components": [
            {
                "type": "library",
                "name": dep,
            }
            for dep in dependencies
        ],
    }
    if not dry_run:
        output.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    return output


def write_provenance(
    project_name: str,
    version: str,
    artifacts: list[Artifact],
    *,
    dry_run: bool,
) -> Path:
    if not dry_run:
        RELEASE_META_DIR.mkdir(parents=True, exist_ok=True)
    output = RELEASE_META_DIR / f"{project_name}-{version}.provenance.json"
    commit = run(["git", "rev-parse", "HEAD"], dry_run=dry_run)
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], dry_run=dry_run)
    remote = run(["git", "remote", "get-url", "origin"], dry_run=dry_run, check=False)

    payload = {
        "project": project_name,
        "version": version,
        "tag": f"v{version}",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "git": {
            "commit": commit,
            "branch": branch,
            "origin": remote,
        },
        "build": {
            "python": sys.version,
            "platform": platform.platform(),
            "cwd": str(PROJECT_ROOT),
        },
        "artifacts": [
            {
                "name": a.name,
                "path": str(a.path.relative_to(PROJECT_ROOT)),
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
            }
            for a in artifacts
        ],
    }
    if not dry_run:
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def build_release_notes(version: str, changelog_body: str, *, dry_run: bool) -> Path:
    if not dry_run:
        RELEASE_META_DIR.mkdir(parents=True, exist_ok=True)
    output = RELEASE_META_DIR / f"release-notes-v{version}.md"
    notes = textwrap.dedent(
        f"""\
        ## netset2p2p v{version}

        ### Changelog

        {changelog_body.strip()}

        ### Supply Chain Artifacts

        - `SHA256SUMS`
        - `*.sbom.cdx.json` (CycloneDX)
        - `*.provenance.json`
        """
    )
    if not dry_run:
        output.write_text(notes, encoding="utf-8")
    return output


def git_commit_tag_push(version: str, *, dry_run: bool) -> None:
    tag = f"v{version}"
    run(["git", "add", "pyproject.toml", "CHANGELOG.md", "README.md"], dry_run=dry_run)
    run(["git", "commit", "-m", f"chore(release): {tag}"], dry_run=dry_run)
    run(["git", "tag", tag], dry_run=dry_run)
    run(["git", "push", "origin", "HEAD"], dry_run=dry_run)
    run(["git", "push", "origin", tag], dry_run=dry_run)


def create_github_release(
    version: str, files: list[Path], notes_file: Path, *, dry_run: bool
) -> None:
    tag = f"v{version}"
    cmd = [
        "gh",
        "release",
        "create",
        tag,
        "--title",
        f"{tag}",
        "--notes-file",
        str(notes_file),
    ] + [str(f) for f in files]
    run(cmd, dry_run=dry_run)


def main() -> int:
    args = parse_args()

    try:
        versions = resolve_versions(args)
        ensure_clean_git_tree(allow_dirty=args.allow_dirty, dry_run=args.dry_run)
        ensure_tooling_available(skip_checks=args.skip_checks, dry_run=args.dry_run)

        update_pyproject_version(versions.next, dry_run=args.dry_run)
        update_readme_badge_version(versions.next, dry_run=args.dry_run)
        changelog_body = update_changelog(versions.next, dry_run=args.dry_run)

        run_quality_checks(skip_checks=args.skip_checks, dry_run=args.dry_run)
        ensure_build_module(dry_run=args.dry_run)

        artifacts_paths = build_artifacts(dry_run=args.dry_run)
        artifacts = collect_artifacts(artifacts_paths) if not args.dry_run else []

        sha_file = write_sha256sums(artifacts, dry_run=args.dry_run)

        metadata = read_project_metadata().get("project", {})
        project_name = str(metadata.get("name", "netset2p2p"))
        deps_raw = metadata.get("dependencies", [])
        dependencies = [str(dep) for dep in deps_raw] if isinstance(deps_raw, list) else []

        sbom_file = write_sbom(project_name, versions.next, dependencies, dry_run=args.dry_run)
        prov_file = write_provenance(project_name, versions.next, artifacts, dry_run=args.dry_run)
        notes_file = build_release_notes(versions.next, changelog_body, dry_run=args.dry_run)

        release_files = artifacts_paths + [sha_file, sbom_file, prov_file]
        git_commit_tag_push(versions.next, dry_run=args.dry_run)
        create_github_release(versions.next, release_files, notes_file, dry_run=args.dry_run)

        print(f"Release {versions.next} complete.")
        return 0
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
