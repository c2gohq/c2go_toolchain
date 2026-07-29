#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

"""Build the recursively complete, deterministic C2Go release source bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from release_version import validate_release_version


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "toolchain.lock.json"


def fail(message: str) -> None:
    raise SystemExit(f"package-source: {message}")


def run_git(repository: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        fail(f"git {' '.join(args)} failed in {repository}: {detail}")
    return proc.stdout.strip()


def load_lock() -> dict[str, Any]:
    try:
        return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {LOCK_PATH}: {exc}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_date_epoch() -> int:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    if value is None:
        value = run_git(ROOT, "show", "-s", "--format=%ct", "HEAD")
    try:
        epoch = int(value)
    except ValueError:
        fail(f"SOURCE_DATE_EPOCH must be an integer, got {value!r}")
    if epoch < 0:
        fail("SOURCE_DATE_EPOCH must not be negative")
    return epoch


def tracked_entries(repository: Path) -> Iterator[tuple[str, Path]]:
    proc = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        fail(f"git ls-files failed in {repository}: {proc.stderr.decode().strip()}")

    entries: list[tuple[str, Path]] = []
    for record in proc.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, _, raw_stage = metadata.split()
        except ValueError:
            fail(f"cannot parse git index entry in {repository}: {record!r}")
        mode = raw_mode.decode("ascii")
        stage = raw_stage.decode("ascii")
        if stage != "0":
            fail(f"unmerged index entry in {repository}: {os.fsdecode(raw_path)}")
        if mode == "160000":
            continue
        relative = Path(os.fsdecode(raw_path))
        pure = PurePosixPath(relative.as_posix())
        if pure.is_absolute() or ".." in pure.parts:
            fail(f"unsafe tracked path in {repository}: {relative}")
        entries.append((mode, relative))
    yield from sorted(entries, key=lambda item: item[1].as_posix())


def base_info(name: str, mode: int, epoch: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mode = mode
    info.mtime = epoch
    return info


def add_bytes(
    archive: tarfile.TarFile,
    name: str,
    payload: bytes,
    epoch: int,
    mode: int = 0o644,
) -> None:
    info = base_info(name, mode, epoch)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def add_repository(
    archive: tarfile.TarFile,
    repository: Path,
    archive_prefix: str,
    epoch: int,
) -> int:
    count = 0
    for mode, relative in tracked_entries(repository):
        source = repository / relative
        name = f"{archive_prefix}/{relative.as_posix()}"
        if mode == "120000":
            if not source.is_symlink():
                fail(f"tracked symlink is not checked out as a symlink: {source}")
            info = base_info(name, 0o777, epoch)
            info.type = tarfile.SYMTYPE
            info.linkname = os.readlink(source)
            archive.addfile(info)
        elif mode in {"100644", "100755"}:
            if not source.is_file():
                fail(f"tracked source file is missing: {source}")
            info = base_info(name, 0o755 if mode == "100755" else 0o644, epoch)
            info.size = source.stat().st_size
            with source.open("rb") as payload:
                archive.addfile(info, payload)
        else:
            fail(f"unsupported git mode {mode} for {source}")
        count += 1
    return count


def repository_layout(lock: dict[str, Any]) -> list[dict[str, Any]]:
    components = {
        item.get("name"): item
        for item in lock.get("components", [])
        if isinstance(item, dict)
    }
    nested = {
        item.get("name"): item
        for item in lock.get("nested_dependencies", [])
        if isinstance(item, dict)
    }
    rows = [
        {
            "name": "c2go-toolchain",
            "repository": ROOT,
            "archive_path": "c2go-toolchain",
            "revision": run_git(ROOT, "rev-parse", "HEAD"),
        },
        {
            "name": "c2go-clang",
            "repository": ROOT / "components/c2go-clang",
            "archive_path": "c2go-toolchain/components/c2go-clang",
            "revision": components.get("c2go-clang", {}).get("revision"),
        },
        {
            "name": "c2go-bind",
            "repository": ROOT / "components/c2go-bind",
            "archive_path": "c2go-toolchain/components/c2go-bind",
            "revision": components.get("c2go-bind", {}).get("revision"),
        },
        {
            "name": "c2go-libc",
            "repository": ROOT / "components/c2go-libc",
            "archive_path": "c2go-toolchain/components/c2go-libc",
            "revision": components.get("c2go-libc", {}).get("revision"),
        },
        {
            "name": "musl",
            "repository": ROOT / "components/c2go-libc/musl",
            "archive_path": "c2go-toolchain/components/c2go-libc/musl",
            "revision": nested.get("musl", {}).get("revision"),
        },
    ]
    for row in rows:
        repository = row["repository"]
        revision = row["revision"]
        if not repository.is_dir():
            fail(f"source repository is missing: {repository}")
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            fail(f"{row['name']} has no full locked revision")
        actual = run_git(repository, "rev-parse", "HEAD")
        if actual != revision:
            fail(f"{row['name']} checkout {actual} does not match lock {revision}")
    return rows


def source_readme(version: str) -> bytes:
    return f"""# C2Go Toolchain {version} source bundle

This archive is the recursively complete source snapshot distributed with the
matching C2Go Toolchain release. `SOURCE-INFO.json` records every repository
revision. Submodule gitlinks under `c2go-toolchain/components/` are represented
by their expanded source directories, including the nested c2go-libc musl fork.

The release build definition is under
`c2go-toolchain/.github/workflows/release.yml`; packaging and release gates are
under `c2go-toolchain/scripts/`. Each source tree retains its own license and
third-party notices. Inclusion in this archive does not relicense a component.
""".encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", default=ROOT / "dist", type=Path)
    args = parser.parse_args()

    version_error = validate_release_version(args.version)
    if version_error is not None:
        fail(f"invalid version {args.version!r}: {version_error}")

    lock = load_lock()
    epoch = source_date_epoch()
    repositories = repository_layout(lock)
    archive_root = f"c2go-toolchain-{args.version}-source"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = args.output_dir / f"{archive_root}.tar.gz"

    source_info = {
        "schema_version": 1,
        "version": args.version,
        "source_date_epoch": epoch,
        "repositories": [
            {
                "name": row["name"],
                "archive_path": row["archive_path"],
                "revision": row["revision"],
            }
            for row in repositories
        ],
        "toolchain_lock": lock,
    }

    with archive_path.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_output,
            compresslevel=6,
            mtime=epoch,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w|",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                add_bytes(
                    archive,
                    f"{archive_root}/SOURCE-README.md",
                    source_readme(args.version),
                    epoch,
                )
                add_bytes(
                    archive,
                    f"{archive_root}/SOURCE-INFO.json",
                    (json.dumps(source_info, indent=2, sort_keys=True) + "\n").encode(),
                    epoch,
                )
                for row in repositories:
                    count = add_repository(
                        archive,
                        row["repository"],
                        f"{archive_root}/{row['archive_path']}",
                        epoch,
                    )
                    if count == 0:
                        fail(f"{row['name']} contributed no tracked source files")

    checksum = sha256_file(archive_path)
    checksum_path = archive_path.with_name(archive_path.name + ".sha256")
    checksum_path.write_text(f"{checksum}  {archive_path.name}\n", encoding="utf-8")
    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
