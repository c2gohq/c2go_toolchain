#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

"""Fail-closed validation for a coordinated C2Go toolchain release."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from release_version import validate_release_version


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "toolchain.lock.json"

EXPECTED_COMPONENTS = {
    "c2go-clang": (
        "https://github.com/c2gohq/c2go_clang.git",
        "components/c2go-clang",
    ),
    "c2go-bind": (
        "https://github.com/c2gohq/c2go_bind.git",
        "components/c2go-bind",
    ),
    "c2go-libc": (
        "https://github.com/c2gohq/c2go_libc.git",
        "components/c2go-libc",
    ),
}

EXPECTED_MUSL = {
    "name": "musl",
    "repository": "https://github.com/c2gohq/musl.git",
    "owner_component": "c2go-libc",
    "relative_path": "musl",
    "path": "components/c2go-libc/musl",
}


def run_git(*args: str, cwd: Path = ROOT) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def load_lock(errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {LOCK_PATH.name}: {exc}")
        return {}
    if data.get("schema_version") != 1:
        errors.append("toolchain.lock.json schema_version must be 1")
    return data


def validate_structure(lock: dict[str, Any], errors: list[str]) -> None:
    components = lock.get("components")
    if not isinstance(components, list):
        errors.append("components must be a list")
        return

    seen: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            errors.append("each component must be an object")
            continue
        name = component.get("name")
        if name not in EXPECTED_COMPONENTS:
            errors.append(f"unexpected component: {name!r}")
            continue
        if name in seen:
            errors.append(f"duplicate component: {name}")
            continue
        seen.add(name)
        expected_repo, expected_path = EXPECTED_COMPONENTS[name]
        if component.get("repository") != expected_repo:
            errors.append(f"{name}: repository must be {expected_repo}")
        if component.get("path") != expected_path:
            errors.append(f"{name}: path must be {expected_path}")

    missing = sorted(set(EXPECTED_COMPONENTS) - seen)
    if missing:
        errors.append(f"missing components: {', '.join(missing)}")

    nested = lock.get("nested_dependencies")
    if not isinstance(nested, list) or len(nested) != 1:
        errors.append("nested_dependencies must contain exactly the musl entry")
        return
    musl = nested[0]
    for key, value in EXPECTED_MUSL.items():
        if musl.get(key) != value:
            errors.append(f"musl: {key} must be {value!r}")


def valid_revision(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def find_submodule(repo: Path, relative_path: str) -> tuple[str, str]:
    modules = repo / ".gitmodules"
    if not modules.is_file():
        raise RuntimeError(f"{modules} is missing")
    rows = run_git(
        "config",
        "-f",
        str(modules),
        "--get-regexp",
        r"^submodule\..*\.path$",
        cwd=repo,
    ).splitlines()
    for row in rows:
        key, value = row.split(None, 1)
        if value == relative_path:
            prefix = key[: -len(".path")]
            url = run_git("config", "-f", str(modules), "--get", f"{prefix}.url", cwd=repo)
            return prefix, url
    raise RuntimeError(f"no submodule maps to {relative_path!r} in {modules}")


def verify_gitlink(
    repo: Path,
    relative_path: str,
    full_path: Path,
    expected_url: str,
    expected_revision: str,
    errors: list[str],
) -> None:
    try:
        _, actual_url = find_submodule(repo, relative_path)
        if actual_url != expected_url:
            errors.append(f"{relative_path}: URL {actual_url!r} != {expected_url!r}")

        stage = run_git("ls-files", "--stage", "--", relative_path, cwd=repo)
        fields = stage.split()
        if len(fields) < 4 or fields[0] != "160000":
            errors.append(f"{relative_path}: not recorded as a submodule gitlink")
        elif fields[1] != expected_revision:
            errors.append(
                f"{relative_path}: gitlink {fields[1]} != lock revision {expected_revision}"
            )

        actual_revision = run_git("rev-parse", "HEAD", cwd=full_path)
        if actual_revision != expected_revision:
            errors.append(
                f"{relative_path}: checkout {actual_revision} != lock revision {expected_revision}"
            )
        dirty = run_git("status", "--porcelain", cwd=full_path)
        if dirty:
            errors.append(f"{relative_path}: working tree is dirty")
    except (OSError, RuntimeError) as exc:
        errors.append(f"{relative_path}: {exc}")


def resolve_remote_tag(repository: str, tag: str) -> str:
    output = run_git(
        "ls-remote",
        "--tags",
        repository,
        f"refs/tags/{tag}",
        f"refs/tags/{tag}^{{}}",
    )
    refs: dict[str, str] = {}
    for row in output.splitlines():
        fields = row.split()
        if len(fields) == 2:
            refs[fields[1]] = fields[0]
    peeled = refs.get(f"refs/tags/{tag}^{{}}")
    direct = refs.get(f"refs/tags/{tag}")
    revision = peeled or direct
    if revision is None:
        raise RuntimeError(f"tag {tag!r} is not present at {repository}")
    return revision


def validate_snapshot(lock: dict[str, Any], errors: list[str]) -> None:
    components = lock.get("components", [])
    by_name = {item.get("name"): item for item in components if isinstance(item, dict)}
    for name, (repository, path) in EXPECTED_COMPONENTS.items():
        component = by_name.get(name, {})
        revision = component.get("revision")
        if not valid_revision(revision):
            errors.append(f"{name}: revision must be a full lowercase 40-hex commit")
            continue
        verify_gitlink(
            ROOT,
            path,
            ROOT / path,
            repository,
            revision,
            errors,
        )

    nested = lock.get("nested_dependencies", [])
    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
        musl = nested[0]
        revision = musl.get("revision")
        if not valid_revision(revision):
            errors.append("musl: revision must be a full lowercase 40-hex commit")
        elif (ROOT / "components/c2go-libc").is_dir():
            verify_gitlink(
                ROOT / "components/c2go-libc",
                EXPECTED_MUSL["relative_path"],
                ROOT / EXPECTED_MUSL["path"],
                EXPECTED_MUSL["repository"],
                revision,
                errors,
            )

    try:
        recursive = run_git("submodule", "status", "--recursive")
        for line in recursive.splitlines():
            if line and line[0] in "-+U":
                errors.append(f"recursive submodule is not pinned/initialized: {line}")
        if run_git("status", "--porcelain"):
            errors.append("c2go-toolchain working tree is dirty")
    except RuntimeError as exc:
        errors.append(str(exc))


def validate_release_metadata(lock: dict[str, Any], errors: list[str]) -> None:
    release = lock.get("release")
    version: object = None
    if not isinstance(release, dict):
        errors.append("release must be an object")
    else:
        version = release.get("version")
        version_error = validate_release_version(version)
        if version_error is not None:
            errors.append(f"release.version is invalid: {version_error}")
        if release.get("status") not in {"release-candidate", "stable"}:
            errors.append("release.status must be release-candidate or stable")
        published_at = release.get("published_at")
        if not isinstance(published_at, str):
            errors.append("release.published_at must be an ISO-8601 string")
        else:
            try:
                parsed = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("timezone is required")
            except ValueError:
                errors.append("release.published_at must be a timezone-aware ISO-8601 string")

    components = lock.get("components", [])
    by_name = {item.get("name"): item for item in components if isinstance(item, dict)}
    for name in EXPECTED_COMPONENTS:
        component = by_name.get(name, {})
        revision = component.get("revision")
        tag = component.get("tag")
        if not valid_revision(revision):
            continue
        if not isinstance(tag, str) or not tag:
            errors.append(f"{name}: tag must be set")
            continue
        if isinstance(version, str) and tag != version:
            errors.append(f"{name}: tag {tag!r} must match release.version {version!r}")
        try:
            tagged_revision = resolve_remote_tag(EXPECTED_COMPONENTS[name][0], tag)
            if tagged_revision != revision:
                errors.append(
                    f"{name}: remote tag {tag} resolves to {tagged_revision}, not {revision}"
                )
        except RuntimeError as exc:
            errors.append(f"{name}: {exc}")

    nested = lock.get("nested_dependencies", [])
    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
        musl = nested[0]
        revision = musl.get("revision")
        tag = musl.get("tag")
        if not valid_revision(revision):
            pass
        elif not isinstance(tag, str) or not tag:
            errors.append("musl: tag must be set")
        else:
            try:
                tagged_revision = resolve_remote_tag(EXPECTED_MUSL["repository"], tag)
                if tagged_revision != revision:
                    errors.append(
                        f"musl: remote tag {tag} resolves to {tagged_revision}, not {revision}"
                    )
            except RuntimeError as exc:
                errors.append(f"musl: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="validate the pre-release manifest shape without requiring submodules",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="validate pinned revisions and clean recursive submodules without requiring release tags",
    )
    args = parser.parse_args()

    if args.structure_only and args.snapshot:
        parser.error("--structure-only and --snapshot are mutually exclusive")

    errors: list[str] = []
    lock = load_lock(errors)
    if lock:
        validate_structure(lock, errors)
        if not args.structure_only:
            validate_snapshot(lock, errors)
        if not args.structure_only and not args.snapshot:
            validate_release_metadata(lock, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.structure_only:
        print("C2Go toolchain scaffold structure: OK")
    elif args.snapshot:
        print("C2Go pinned toolchain snapshot: OK")
    else:
        print("C2Go coordinated release gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
