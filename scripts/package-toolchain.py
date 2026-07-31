#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

"""Build a deterministic binary archive for one native C2Go target."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import platform as host_platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from release_version import validate_release_version


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "toolchain.lock.json"

TARGETS = {
    "linux-amd64": ("Linux", {"x86_64", "amd64"}, ".tar.gz"),
    "linux-arm64": ("Linux", {"aarch64", "arm64"}, ".tar.gz"),
    "windows-amd64": ("Windows", {"amd64", "x86_64"}, ".zip"),
    "macos-arm64": ("Darwin", {"arm64", "aarch64"}, ".tar.gz"),
}

SDK_DOCS = (
    ("SDK-README.md", "README.md"),
    ("SDK-README.zh-CN.md", "README.zh-CN.md"),
)

TOOLCHAIN_LEGAL_DOCS = (
    "LICENSE",
    "NOTICE",
    "LICENSING.md",
    "LICENSING.zh-CN.md",
    "COMMERCIAL-LICENSING.md",
    "COMMERCIAL-LICENSING.zh-CN.md",
    "TRADEMARKS.md",
    "toolchain.lock.json",
)

CLANG_DOCS = (
    "LICENSE.TXT",
    "NOTICE",
    "C2GO-LICENSING.md",
    "C2GO-LICENSING.zh-CN.md",
)

BIND_DOCS = (
    "LICENSE",
    "NOTICE",
    "LICENSING.md",
    "LICENSING.zh-CN.md",
    "COMMERCIAL-LICENSING.md",
    "COMMERCIAL-LICENSING.zh-CN.md",
    "PROVENANCE.md",
    "THIRD_PARTY_NOTICES.md",
)

LIBC_DOCS = BIND_DOCS


def fail(message: str) -> None:
    raise SystemExit(f"package-toolchain: {message}")


def run(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        fail(f"{' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def load_lock() -> dict[str, Any]:
    try:
        return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {LOCK_PATH}: {exc}")


def verify_host(target: str) -> None:
    expected_system, expected_machines, _ = TARGETS[target]
    actual_system = host_platform.system()
    actual_machine = host_platform.machine().lower()
    if actual_system != expected_system or actual_machine not in expected_machines:
        fail(
            f"target {target} requires a native {expected_system}/"
            f"{sorted(expected_machines)} runner; got {actual_system}/{actual_machine}"
        )


def find_binary(build_dir: Path, name: str, windows: bool) -> Path:
    suffix = ".exe" if windows else ""
    candidates = (
        build_dir / "bin" / f"{name}{suffix}",
        build_dir / "Release" / "bin" / f"{name}{suffix}",
        build_dir / "bin" / "Release" / f"{name}{suffix}",
    )
    for candidate in candidates:
        if candidate.is_file() or candidate.is_symlink():
            return candidate.resolve()
    fail(f"cannot find {name}{suffix} below {build_dir}")


def copy_file(source: Path, destination: Path, executable: bool = False) -> None:
    if not source.is_file():
        fail(f"required file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    mode = destination.stat().st_mode
    if executable:
        destination.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def render_text_file(source: Path, destination: Path, replacements: dict[str, str]) -> None:
    if not source.is_file():
        fail(f"required file is missing: {source}")
    text = source.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        fail(f"required directory is missing: {source}")
    shutil.copytree(source, destination, symlinks=True)


def copy_tracked_subtree(
    repository: Path, subtree: Path, destination: Path
) -> None:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--", subtree.as_posix()],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if output.returncode != 0:
        fail(f"git ls-files failed in {repository}: {output.stderr.decode().strip()}")
    copied = 0
    for raw_path in output.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        try:
            installed_relative = relative.relative_to(subtree)
        except ValueError:
            fail(f"tracked path {relative} escapes requested subtree {subtree}")
        source = repository / relative
        target = destination / installed_relative
        if source.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            copy_file(source, target, bool(source.stat().st_mode & stat.S_IXUSR))
        else:
            fail(f"tracked SDK file is missing or unsupported: {source}")
        copied += 1
    if copied == 0:
        fail(f"tracked SDK subtree is empty: {repository}/{subtree}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_date_epoch() -> int:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    if value is None:
        value = run("git", "show", "-s", "--format=%ct", "HEAD", cwd=ROOT)
    try:
        epoch = int(value)
    except ValueError:
        fail(f"SOURCE_DATE_EPOCH must be an integer, got {value!r}")
    if epoch < 315532800:  # ZIP timestamps cannot predate 1980-01-01.
        epoch = 315532800
    return epoch


def stable_version_lines(output: str) -> list[str]:
    """Drop build-directory details that make metadata host-specific."""
    return [line for line in output.splitlines() if not line.startswith("InstalledDir:")]


def normalized_tar(source: Path, output: Path, epoch: int) -> None:
    temporary_tar = output.with_suffix("")
    with tarfile.open(temporary_tar, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(source.rglob("*")):
            arcname = path.relative_to(source.parent).as_posix()
            info = archive.gettarinfo(str(path), arcname)
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = epoch
            if path.is_file() and not path.is_symlink():
                with path.open("rb") as payload:
                    archive.addfile(info, payload)
            else:
                archive.addfile(info)
    with temporary_tar.open("rb") as payload, output.open("wb") as compressed:
        with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=epoch) as zipper:
            shutil.copyfileobj(payload, zipper)
    temporary_tar.unlink()


def normalized_zip(source: Path, output: Path, epoch: int) -> None:
    timestamp = dt.datetime.fromtimestamp(epoch, dt.timezone.utc)
    zip_time = (timestamp.year, timestamp.month, timestamp.day,
                timestamp.hour, timestamp.minute, timestamp.second)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source.parent).as_posix()
            if path.is_dir():
                relative += "/"
            info = zipfile.ZipInfo(relative, zip_time)
            info.create_system = 3
            mode = path.lstat().st_mode
            info.external_attr = (mode & 0xFFFF) << 16
            if path.is_dir():
                archive.writestr(info, b"")
            elif path.is_symlink():
                archive.writestr(info, os.readlink(path).encode())
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--target", required=True, choices=sorted(TARGETS))
    parser.add_argument("--clang-build-dir", required=True, type=Path)
    parser.add_argument("--c2go-bind", required=True, type=Path)
    parser.add_argument("--output-dir", default=ROOT / "dist", type=Path)
    args = parser.parse_args()

    version_error = validate_release_version(args.version)
    if version_error is not None:
        fail(f"invalid version {args.version!r}: {version_error}")
    verify_host(args.target)

    windows = args.target.startswith("windows-")
    executable_suffix = ".exe" if windows else ""
    clang = find_binary(args.clang_build_dir.resolve(), "clang", windows)
    c2go_lto = find_binary(args.clang_build_dir.resolve(), "c2go-lto", windows)
    c2go_bind = args.c2go_bind.resolve()
    if not c2go_bind.is_file():
        fail(f"c2go-bind binary is missing: {c2go_bind}")

    lock = load_lock()
    clang_version = run(str(clang), "--version")
    c2go_lto_version = run(str(c2go_lto), "--version")
    bind_version = run(str(c2go_bind), "--version")
    expected_bind_version = f"c2go-bind {args.version}"
    if bind_version != expected_bind_version:
        fail(
            f"c2go-bind reports {bind_version!r}; expected {expected_bind_version!r}"
        )
    clang_revision = next(
        (
            component.get("revision")
            for component in lock.get("components", [])
            if component.get("name") == "c2go-clang"
        ),
        None,
    )
    if not isinstance(clang_revision, str) or clang_revision[:12] not in clang_version:
        fail(
            "clang --version does not identify the locked c2go-clang revision "
            f"{clang_revision!r}"
        )
    resource_dir = Path(run(str(clang), "-print-resource-dir")).resolve()
    if not (resource_dir / "include" / "c2go.h").is_file():
        fail(f"c2go.h is missing from Clang resource directory {resource_dir}")

    epoch = source_date_epoch()
    archive_root_name = f"c2go-toolchain-{args.version}-{args.target}"
    _, _, archive_suffix = TARGETS[args.target]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = args.output_dir / f"{archive_root_name}{archive_suffix}"

    with tempfile.TemporaryDirectory(prefix="c2go-toolchain-package-") as temporary:
        package_root = Path(temporary) / archive_root_name
        bin_dir = package_root / "bin"
        copy_file(
            clang, bin_dir / f"c2go-clang{executable_suffix}", executable=True
        )
        copy_file(c2go_lto, bin_dir / f"c2go-lto{executable_suffix}", executable=True)
        copy_file(c2go_bind, bin_dir / f"c2go-bind{executable_suffix}", executable=True)
        installed_resource_dir = package_root / "lib" / "clang" / resource_dir.name
        copy_tree(resource_dir, installed_resource_dir)

        libc_source = ROOT / "components" / "c2go-libc"
        copy_tracked_subtree(
            libc_source, Path("csrc/include"), package_root / "include"
        )
        copy_file(
            resource_dir / "include" / "c2go.h",
            package_root / "include" / "c2go.h",
        )
        # c2go.h is a public SDK header.  Keep its canonical installed copy in
        # <prefix>/include rather than duplicating it in the Clang resource tree.
        (installed_resource_dir / "include" / "c2go.h").unlink()

        for source_name, installed_name in SDK_DOCS:
            render_text_file(
                ROOT / source_name,
                package_root / installed_name,
                {"@C2GO_VERSION@": args.version},
            )
        for name in TOOLCHAIN_LEGAL_DOCS:
            copy_file(ROOT / name, package_root / name)

        clang_source = ROOT / "components" / "c2go-clang"
        clang_license_dir = package_root / "licenses" / "c2go-clang"
        for name in CLANG_DOCS:
            candidate = clang_source / name
            if candidate.is_file():
                copy_file(candidate, clang_license_dir / name)

        bind_source = ROOT / "components" / "c2go-bind"
        bind_license_dir = package_root / "licenses" / "c2go-bind"
        for name in BIND_DOCS:
            copy_file(bind_source / name, bind_license_dir / name)
        copy_tracked_subtree(
            bind_source, Path("LICENSES"), bind_license_dir / "LICENSES"
        )

        libc_license_dir = package_root / "licenses" / "c2go-libc"
        for name in LIBC_DOCS:
            copy_file(libc_source / name, libc_license_dir / name)
        copy_tracked_subtree(
            libc_source, Path("LICENSES"), libc_license_dir / "LICENSES"
        )

        musl_copyright = libc_source / "musl" / "COPYRIGHT"
        if musl_copyright.is_file():
            copy_file(musl_copyright, package_root / "licenses" / "musl" / "COPYRIGHT")

        binaries = {}
        for binary in sorted(bin_dir.iterdir()):
            binaries[binary.name] = sha256_file(binary)
        build_info = {
            "schema_version": 2,
            "layout": "c2go-sdk-v1",
            "version": args.version,
            "target": args.target,
            "source_date_epoch": epoch,
            "clang_version": stable_version_lines(clang_version),
            "c2go_lto_version": stable_version_lines(c2go_lto_version),
            "c2go_bind_version": bind_version,
            "components": lock.get("components", []),
            "nested_dependencies": lock.get("nested_dependencies", []),
            "c2go_libc_module": {
                "path": "github.com/c2gohq/c2go_libc",
                "version": args.version,
            },
            "binaries_sha256": binaries,
        }
        (package_root / "BUILD-INFO.json").write_text(
            json.dumps(build_info, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if archive_suffix == ".zip":
            normalized_zip(package_root, archive_path, epoch)
        else:
            normalized_tar(package_root, archive_path, epoch)

    checksum = sha256_file(archive_path)
    checksum_path = archive_path.with_name(archive_path.name + ".sha256")
    checksum_path.write_bytes(f"{checksum}  {archive_path.name}\n".encode("ascii"))
    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
