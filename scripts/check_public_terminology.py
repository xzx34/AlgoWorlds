#!/usr/bin/env python3
"""Reject retired project and metric names from the curated public surface."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".gitleaks.toml",
    "README.md",
    "CONTRIBUTING.md",
    "DATA_LICENSE",
    "NOTICE",
    "PUBLIC_RELEASE_MANIFEST.json",
    "SECURITY.md",
    "MANIFEST.in",
    "LICENSE",
    "pytest.ini",
    "pyproject.toml",
    "release-policy.toml",
)
PUBLIC_TREES = (".github", "algoworlds", "docs", "examples", "scripts", "tests")
TEXT_SUFFIXES = frozenset(
    {
        ".astro",
        ".css",
        ".html",
        ".js",
        ".json",
        ".md",
        ".mjs",
        ".py",
        ".svg",
        ".toml",
        ".ts",
        ".txt",
        ".yaml",
        ".yml",
    }
)
GLOBAL_FORBIDDEN = (
    ("retired benchmark name", re.compile(r"core" + r"[\s_-]?240", re.IGNORECASE)),
    ("legacy project identity", re.compile(r"\btool" + r"trek(?:\b|_)", re.IGNORECASE)),
    ("internal transport", re.compile(r"\bi" + r"chat\b", re.IGNORECASE)),
    ("wrong organization", re.compile(r"\bwe" + r"chat\s+ai\b", re.IGNORECASE)),
    ("private source repository", re.compile(r"xzx34/ten" + r"cent", re.IGNORECASE)),
    ("private local path", re.compile(r"/(?:Users|home)/[^/\s]+/", re.IGNORECASE)),
    ("named author", re.compile(r"\bzi" + r"xiang\s+xu\b", re.IGNORECASE)),
    ("named author", re.compile(r"\bji" + r"aan\s+wang\b", re.IGNORECASE)),
    ("named author", re.compile(r"\bfan" + r"dong\s+meng\b", re.IGNORECASE)),
)
EVALUATOR_FORBIDDEN = (
    ("retired score field", re.compile(r"\bcase" + r"_score\b", re.IGNORECASE)),
    ("non-public metric", re.compile(r"\breference" + r" utility\b", re.IGNORECASE)),
    ("non-public metric", re.compile(r"\binformation" + r" sufficiency\b", re.IGNORECASE)),
    ("non-public metric", re.compile(r"\bdiscovery" + r" coverage\b", re.IGNORECASE)),
)
ARTIFACT_FIELD_FORBIDDEN = (
    "case" + "_score",
    "construction_coordinate",
    "construction_evidence",
    "construction_nonce",
    "construction_version",
    "coordinate_generation",
    "coordinate_seed_digest",
    "discovery" + "_coverage",
    "discovery_floor",
    "information" + "_sufficiency",
    "normalized" + "_regret",
    "reference" + "_utility",
)


def public_paths(root: Path = ROOT) -> tuple[Path, ...]:
    paths = [root / relative for relative in ROOT_FILES]
    for relative in PUBLIC_TREES:
        paths.extend(
            path
            for path in (root / relative).rglob("*")
            if path.is_file()
            and path.suffix in TEXT_SUFFIXES
            and "__pycache__" not in path.parts
        )
    paths.extend(
        path
        for path in (root / "benchmark").rglob("*")
        if path.is_file()
        and path.suffix in TEXT_SUFFIXES
        and "__pycache__" not in path.parts
    )
    for relative in ("src", "public", "docs", "tests"):
        paths.extend(
            path
            for path in (root / "website" / relative).rglob("*")
            if path.is_file() and path.suffix in TEXT_SUFFIXES
        )
    paths.append(root / "website" / "README.md")
    for relative in (
        ".nvmrc",
        "astro.config.mjs",
        "package-lock.json",
        "package.json",
        "playwright.config.ts",
        "tsconfig.json",
    ):
        paths.append(root / "website" / relative)
    return tuple(sorted(set(paths)))


def violations(paths: Iterable[Path]) -> list[str]:
    problems: list[str] = []
    for path in paths:
        if not path.is_file():
            problems.append(f"missing public source: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        patterns = list(GLOBAL_FORBIDDEN)
        is_website = "website" in path.relative_to(ROOT).parts
        if not is_website:
            patterns.extend(EVALUATOR_FORBIDDEN)
        if path.suffix == ".json" and "benchmark" in path.relative_to(ROOT).parts:
            patterns.extend(
                (
                    "non-public artifact field",
                    re.compile(rf'"(?:[^"\\]*_)?{re.escape(field)}"\s*:', re.IGNORECASE),
                )
                for field in ARTIFACT_FIELD_FORBIDDEN
            )
        for label, pattern in patterns:
            match = pattern.search(text)
            if match is not None:
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path}:{line}: {label}: {match.group(0)!r}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    paths = (
        tuple(Path(value).resolve() for value in argv)
        if argv
        else public_paths()
    )
    problems = violations(paths)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"Checked {len(paths)} curated public source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
