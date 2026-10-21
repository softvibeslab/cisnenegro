#!/usr/bin/env python3
"""Install explicitly selected portable skills after checking package hashes.

Default: dry run. Existing skills are never overwritten. No network or secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


PACKAGE = Path(__file__).resolve().parents[1]


def verified_skills(names: list[str]) -> list[tuple[str, Path]]:
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    available = {item["id"]: item for item in manifest["skills"]}
    chosen = list(dict.fromkeys(names or available))
    unknown = set(chosen) - available.keys()
    if unknown:
        raise ValueError("Unknown skills: " + ", ".join(sorted(unknown)))
    result = []
    for name in chosen:
        folder = PACKAGE / available[name]["path"]
        if folder.is_symlink() or not folder.is_dir() or PACKAGE not in folder.resolve().parents:
            raise ValueError("Invalid skill directory: " + name)
        actual = set()
        for source in folder.rglob("*"):
            if source.is_symlink():
                raise ValueError("Symbolic links are not allowed: " + source.name)
            if not source.is_file():
                continue
            key = source.relative_to(PACKAGE).as_posix()
            expected = manifest["files"].get(key)
            if not expected or hashlib.sha256(source.read_bytes()).hexdigest() != expected["sha256"]:
                raise ValueError("Package integrity check failed: " + key)
            actual.add(key)
        prefix = available[name]["path"] + "/"
        expected_paths = {key for key in manifest["files"] if key.startswith(prefix)}
        if actual != expected_paths or not (folder / "SKILL.md").is_file():
            raise ValueError("Incomplete skill: " + name)
        result.append((name, folder))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="Destination skills directory")
    parser.add_argument("--skill", action="append", default=[], help="Skill id; repeat to select several")
    parser.add_argument("--install", action="store_true", help="Copy files; otherwise dry run")
    args = parser.parse_args()
    destination = args.dest.expanduser().resolve()
    created: list[Path] = []
    try:
        selections = verified_skills(args.skill)
        if destination == PACKAGE or PACKAGE in destination.parents:
            raise ValueError("Choose a destination outside the ecosystem package")
        for name, _ in selections:
            target = destination / name
            if target.exists() or target.is_symlink():
                raise ValueError("Already exists; no files overwritten: " + str(target))
        if not args.install:
            for name, _ in selections:
                print("Would install:", destination / name)
            print("Dry run only. Add --install to copy these skills.")
            return 0
        destination.mkdir(parents=True, exist_ok=True)
        for name, source in selections:
            target = destination / name
            target.mkdir()  # Exclusive creation protects an existing skill.
            created.append(target)
            shutil.copytree(source, target, dirs_exist_ok=True)
            print("Installed:", target)
        print("Done. No accounts, network services or runtime tools were installed.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        for folder in reversed(created):
            shutil.rmtree(folder)
        print("Error:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
