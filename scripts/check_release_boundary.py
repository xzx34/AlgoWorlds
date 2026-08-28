#!/usr/bin/env python3
"""Enforce the positive source and package allowlists for a public release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "release-policy.toml"
SOURCE_MANIFEST_PATH = ROOT / "PUBLIC_RELEASE_MANIFEST.json"
SOURCE_MANIFEST_SCHEMA = "algoworlds_public_source_manifest/1"


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    chunks: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                chunks.append(".*")
                index += 2
            else:
                chunks.append("[^/]*")
                index += 1
        elif char == "?":
            chunks.append("[^/]")
            index += 1
        else:
            chunks.append(re.escape(char))
            index += 1
    chunks.append("$")
    return re.compile("".join(chunks))


def _matches(path: str, files: set[str], patterns: tuple[str, ...]) -> bool:
    if path in files:
        return True
    return any(_pattern_regex(pattern).fullmatch(path) for pattern in patterns)


def _load_policy() -> dict[str, object]:
    with POLICY_PATH.open("rb") as handle:
        policy = tomllib.load(handle)
    if policy.get("schema_version") != "algoworlds_release_policy/1":
        raise ValueError("unsupported release policy schema")
    return policy


def _tracked_paths() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(
        sorted(value.decode("utf-8") for value in result.stdout.split(b"\0") if value)
    )


def check_source(policy: dict[str, object]) -> list[str]:
    source = policy["source"]
    assert isinstance(source, dict)
    files = set(source["files"])
    patterns = tuple(source["patterns"])
    tracked = _tracked_paths()
    problems = [
        f"source path is outside the positive allowlist: {path}"
        for path in tracked
        if not _matches(path, files, patterns)
    ]
    tracked_set = set(tracked)
    for required in source["required"]:
        if required not in tracked_set:
            problems.append(f"required public source is not tracked: {required}")
    for path in tracked:
        absolute = ROOT / path
        if absolute.is_symlink():
            problems.append(f"public source must not contain symlinks: {path}")
    try:
        manifest = json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        problems.append(f"cannot read public source manifest: {error}")
        return problems
    if not isinstance(manifest, dict):
        problems.append("public source manifest must be a JSON object")
        return problems
    if manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA:
        problems.append("public source manifest has an unsupported schema")
    if manifest.get("digest_algorithm") != "sha256_bytes/1":
        problems.append("public source manifest has an unsupported digest algorithm")
    digests = manifest.get("files")
    if not isinstance(digests, dict):
        problems.append("public source manifest files must be an object")
        return problems
    expected_manifested = tracked_set - {SOURCE_MANIFEST_PATH.name}
    if manifest.get("file_count") != len(digests):
        problems.append("public source manifest file_count is inconsistent")
    if set(digests) != expected_manifested:
        problems.append("public source manifest does not match the tracked source roster")
        return problems
    for relative_path, expected_digest in digests.items():
        if not isinstance(expected_digest, str) or re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None:
            problems.append(f"public source manifest has an invalid digest: {relative_path}")
            continue
        actual_digest = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            problems.append(f"public source manifest digest does not match: {relative_path}")
    return problems


def _safe_member(name: str) -> str:
    normalized = str(PurePosixPath(name))
    if not normalized or normalized == ".":
        return ""
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member: {name!r}")
    return normalized.rstrip("/")


def _strip_sdist_root(paths: list[str]) -> list[str]:
    roots = {PurePosixPath(path).parts[0] for path in paths if path}
    if len(roots) != 1:
        raise ValueError("sdist must contain exactly one top-level directory")
    return ["/".join(PurePosixPath(path).parts[1:]) for path in paths]


def _extract_members(archive: Path, destination: Path) -> tuple[str, list[str]]:
    raw_paths: list[str] = []
    if archive.suffix == ".whl":
        kind = "wheel"
        with zipfile.ZipFile(archive) as package:
            for info in package.infolist():
                path = _safe_member(info.filename)
                if not path or info.is_dir():
                    continue
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise ValueError(f"archive link is forbidden: {path}")
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package.read(info))
                raw_paths.append(path)
    elif archive.name.endswith(".tar.gz"):
        kind = "sdist"
        with tarfile.open(archive, "r:gz") as package:
            for info in package.getmembers():
                path = _safe_member(info.name)
                if not path or info.isdir():
                    continue
                if not info.isfile():
                    raise ValueError(f"archive link or special file is forbidden: {path}")
                source = package.extractfile(info)
                if source is None:
                    raise ValueError(f"cannot read archive member: {path}")
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read())
                raw_paths.append(path)
    else:
        raise ValueError(f"unsupported archive type: {archive}")
    paths = _strip_sdist_root(raw_paths) if kind == "sdist" else raw_paths
    return kind, sorted(path for path in paths if path)


def check_archive(archive: Path, policy: dict[str, object]) -> list[str]:
    problems: list[str] = []
    limit = int(policy["maximum_archive_bytes"])
    if archive.stat().st_size > limit:
        problems.append(
            f"{archive}: archive is {archive.stat().st_size} bytes; limit is {limit}"
        )
    with tempfile.TemporaryDirectory(prefix="algoworlds-package-audit-") as temporary:
        try:
            kind, paths = _extract_members(archive, Path(temporary))
        except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
            return problems + [f"{archive}: {error}"]

    if kind == "wheel":
        files: set[str] = set()
        patterns = tuple(policy["wheel"]["patterns"])
    else:
        source = policy["source"]
        files = set(source["files"])
        patterns = tuple(source["patterns"]) + tuple(
            policy["sdist"]["generated_patterns"]
        )
    problems.extend(
        f"{archive}: package path is outside the positive allowlist: {path}"
        for path in paths
        if not _matches(path, files, patterns)
    )
    basenames = {PurePosixPath(path).name for path in paths}
    for required in ("LICENSE", "DATA_LICENSE", "NOTICE"):
        if required not in basenames:
            problems.append(f"{archive}: missing required notice file: {required}")
    return problems


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("source", help="audit Git-tracked public source paths")
    packages = subparsers.add_parser("packages", help="extract and audit archives")
    packages.add_argument("archives", nargs="+", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    policy = _load_policy()
    if args.command == "source":
        problems = check_source(policy)
        success = "Source release matches the positive allowlist."
    else:
        problems = []
        for archive in args.archives:
            if not archive.is_file():
                problems.append(f"missing archive: {archive}")
                continue
            problems.extend(check_archive(archive, policy))
        success = f"Audited {len(args.archives)} extracted package archives."
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(success)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
