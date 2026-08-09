#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

"""Verify an installed C2Go SDK archive and run an end-to-end smoke test."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from release_version import validate_release_version


ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "linux-amd64": ("x86_64-unknown-linux-goabi", ".tar.gz"),
    "linux-arm64": ("aarch64-unknown-linux-goabi", ".tar.gz"),
    "windows-amd64": ("x86_64-pc-windows-goabi", ".zip"),
    "macos-arm64": ("aarch64-apple-darwin", ".tar.gz"),
}

WINDOWS_UNAVAILABLE_HEADERS = {
    "c2go/mlib/ftw.h",
    "ftw.h",
    "sys/ioctl.h",
    "sys/resource.h",
    "sys/utsname.h",
    "sys/wait.h",
    "termios.h",
}

EXPECTED_TOP_LEVEL = {
    "bin",
    "include",
    "lib",
    "licenses",
    "BUILD-INFO.json",
    "COMMERCIAL-LICENSING.md",
    "COMMERCIAL-LICENSING.zh-CN.md",
    "LICENSE",
    "LICENSING.md",
    "LICENSING.zh-CN.md",
    "NOTICE",
    "README.md",
    "README.zh-CN.md",
    "TRADEMARKS.md",
    "toolchain.lock.json",
}

REQUIRED_LICENSES = {
    "licenses/c2go-clang/LICENSE.TXT",
    "licenses/c2go-clang/NOTICE",
    "licenses/c2go-bind/LICENSE",
    "licenses/c2go-bind/NOTICE",
    "licenses/c2go-bind/THIRD_PARTY_NOTICES.md",
    "licenses/c2go-libc/LICENSE",
    "licenses/c2go-libc/NOTICE",
    "licenses/c2go-libc/THIRD_PARTY_NOTICES.md",
    "licenses/musl/COPYRIGHT",
}


def fail(message: str) -> None:
    raise SystemExit(f"verify-package: {message}")


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        command = " ".join(args)
        detail = proc.stderr.strip() or proc.stdout.strip()
        fail(f"{command} failed ({proc.returncode}): {detail}")
    return proc.stdout.strip()


def validate_member_name(raw_name: str, expected_root: str) -> PurePosixPath:
    if "\\" in raw_name:
        fail(f"archive member uses a non-portable separator: {raw_name!r}")
    name = raw_name.rstrip("/")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        fail(f"unsafe archive member: {raw_name!r}")
    if not path.parts or path.parts[0] != expected_root:
        fail(f"archive member is outside {expected_root}: {raw_name!r}")
    return path


def archive_files(archive: Path, expected_root: str) -> set[str]:
    files: set[str] = set()
    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:gz") as payload:
            for member in payload.getmembers():
                path = validate_member_name(member.name, expected_root)
                if member.isfile() or member.issym() or member.islnk():
                    files.add(path.as_posix())
    elif archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as payload:
            for member in payload.infolist():
                path = validate_member_name(member.filename, expected_root)
                if not member.is_dir():
                    files.add(path.as_posix())
    else:
        fail(f"unsupported archive format: {archive}")
    if not files:
        fail(f"archive has no files: {archive}")
    return files


def extract_archive(archive: Path, destination: Path, expected_root: str) -> Path:
    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:gz") as payload:
            for member in payload.getmembers():
                validate_member_name(member.name, expected_root)
            payload.extractall(destination)
    else:
        with zipfile.ZipFile(archive) as payload:
            for member in payload.infolist():
                validate_member_name(member.filename, expected_root)
            payload.extractall(destination)
            for member in payload.infolist():
                if member.is_dir():
                    continue
                mode = member.external_attr >> 16
                if mode:
                    extracted = destination / PurePosixPath(member.filename)
                    extracted.chmod(mode)
    package_root = destination / expected_root
    if not package_root.is_dir():
        fail(f"archive did not create expected root: {expected_root}")
    return package_root


def tracked_public_headers(libc_source: Path) -> set[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--", "csrc/include"],
        cwd=libc_source,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if output.returncode != 0:
        fail(f"cannot list c2go-libc headers: {output.stderr.decode().strip()}")
    headers = {
        str(PurePosixPath(os.fsdecode(raw)).relative_to("csrc/include"))
        for raw in output.stdout.split(b"\0")
        if raw
    }
    if not headers:
        fail("c2go-libc public header set is empty")
    return headers


def verify_layout(
    files: set[str], version: str, target: str, libc_source: Path
) -> None:
    archive_root = f"c2go-toolchain-{version}-{target}"
    relative_files = {
        str(PurePosixPath(name).relative_to(archive_root)) for name in files
    }
    top_level = {PurePosixPath(name).parts[0] for name in relative_files}
    if top_level != EXPECTED_TOP_LEVEL:
        missing = sorted(EXPECTED_TOP_LEVEL - top_level)
        extra = sorted(top_level - EXPECTED_TOP_LEVEL)
        fail(f"wrong top-level layout; missing={missing}, extra={extra}")

    forbidden_prefixes = ("src/", "components/", "lib/c2go_libc/")
    forbidden = sorted(
        name for name in relative_files if name.startswith(forbidden_prefixes)
    )
    if forbidden:
        fail(f"binary SDK contains source-tree payloads: {forbidden[:10]}")

    expected_headers = tracked_public_headers(libc_source)
    installed_headers = {
        str(PurePosixPath(name).relative_to("include"))
        for name in relative_files
        if name.startswith("include/")
    }
    if installed_headers != expected_headers:
        missing = sorted(expected_headers - installed_headers)
        extra = sorted(installed_headers - expected_headers)
        fail(f"wrong public header set; missing={missing}, extra={extra}")

    resource_c2go_headers = sorted(
        name
        for name in relative_files
        if name.startswith("lib/clang/") and name.endswith("/include/c2go.h")
    )
    if len(resource_c2go_headers) != 1:
        fail(
            "c2go.h must have exactly one compiler-resource copy; "
            f"found={resource_c2go_headers}"
        )

    missing_licenses = sorted(REQUIRED_LICENSES - relative_files)
    if missing_licenses:
        fail(f"required license records are missing: {missing_licenses}")

    executable_suffix = ".exe" if target.startswith("windows-") else ""
    required_binaries = {
        f"bin/c2go-clang{executable_suffix}",
        f"bin/c2go-lto{executable_suffix}",
        f"bin/c2go-bind{executable_suffix}",
    }
    installed_binaries = {
        name for name in relative_files if name.startswith("bin/")
    }
    if installed_binaries != required_binaries:
        missing = sorted(required_binaries - installed_binaries)
        extra = sorted(installed_binaries - required_binaries)
        fail(f"wrong installed tool set; missing={missing}, extra={extra}")


def verify_build_info(package_root: Path, version: str, target: str) -> None:
    try:
        info = json.loads((package_root / "BUILD-INFO.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read BUILD-INFO.json: {exc}")
    if info.get("schema_version") != 2 or info.get("layout") != "c2go-sdk-v1":
        fail("BUILD-INFO.json does not identify the c2go-sdk-v1 layout")
    if info.get("version") != version or info.get("target") != target:
        fail("BUILD-INFO.json version or target does not match the archive")
    expected_module = {
        "path": "github.com/c2gohq/c2go_libc",
        "version": version,
    }
    if info.get("c2go_libc_module") != expected_module:
        fail("BUILD-INFO.json has the wrong c2go-libc module requirement")


def verify_headers(clang: Path, triple: str, target: str, headers: set[str]) -> None:
    unavailable = WINDOWS_UNAVAILABLE_HEADERS if target.startswith("windows-") else set()
    for header in sorted(headers - unavailable):
        run(
            [
                str(clang),
                f"--target={triple}",
                "-fc2go",
                "-fc2go-package=example.com/c2go/sdkcheck",
                "-x",
                "c",
                "-fsyntax-only",
                "-",
            ],
            stdin=f"#include <{header}>\n",
        )


def verify_pipeline(
    package_root: Path, triple: str, target: str, libc_source: Path
) -> None:
    executable_suffix = ".exe" if target.startswith("windows-") else ""
    clang = package_root / "bin" / f"c2go-clang{executable_suffix}"
    c2go_lto = package_root / "bin" / f"c2go-lto{executable_suffix}"
    c2go_bind = package_root / "bin" / f"c2go-bind{executable_suffix}"
    for binary in (clang, c2go_lto, c2go_bind):
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

    run([str(clang), "--version"])
    run([str(c2go_lto), "--version"])
    run([str(c2go_bind), "--version"])

    headers = tracked_public_headers(libc_source)
    verify_headers(clang, triple, target, headers)

    with tempfile.TemporaryDirectory(prefix="c2go-sdk-smoke-") as temporary:
        work = Path(temporary)
        source = work / "input.c"
        assembly = work / "translated.s"
        manifest = work / "translated.json"
        obj = work / "translated.o"
        generated = work / "translated"
        generated.mkdir()
        source.write_text(
            "#include <stdint.h>\n"
            "#include <string.h>\n"
            "#include <c2go.h>\n\n"
            "c2go_extern int add(int a, int b) { return a + b; }\n",
            encoding="utf-8",
        )
        run(
            [
                str(clang),
                f"--target={triple}",
                "-fc2go",
                "-fc2go-package=example.com/c2go/sdkcheck/translated",
                "-O2",
                f"-fc2go-emit-plan9-asm={assembly}",
                f"-fc2go-emit-manifest={manifest}",
                "-c",
                "-o",
                str(obj),
                str(source),
            ],
            cwd=work,
        )
        run(
            [
                str(c2go_bind),
                f"--out={generated}",
                f"--sidecar={manifest}",
                str(assembly),
            ],
            cwd=work,
        )
        (generated / "sdk_test.go").write_text(
            "package translated\n\n"
            'import "testing"\n\n'
            "func TestInstalledSDK(t *testing.T) {\n"
            "\tif got := Add(20, 22); got != 42 {\n"
            '\t\tt.Fatalf("Add(20, 22) = %d, want 42", got)\n'
            "\t}\n"
            "}\n",
            encoding="utf-8",
        )
        go_env = os.environ.copy()
        go_env["GOWORK"] = "off"
        run(["go", "mod", "init", "example.com/c2go/sdkcheck"], cwd=work, env=go_env)
        run(["go", "mod", "edit", "-go=1.25.0"], cwd=work, env=go_env)
        run(
            [
                "go",
                "mod",
                "edit",
                "-require=github.com/c2gohq/c2go_libc@v0.0.0",
                f"-replace=github.com/c2gohq/c2go_libc={libc_source.resolve()}",
            ],
            cwd=work,
            env=go_env,
        )
        run(["go", "mod", "tidy"], cwd=work, env=go_env)
        run(["go", "test", "./..."], cwd=work, env=go_env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--target", required=True, choices=sorted(TARGETS))
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument(
        "--libc-source", default=ROOT / "components" / "c2go-libc", type=Path
    )
    args = parser.parse_args()

    version_error = validate_release_version(args.version)
    if version_error is not None:
        fail(f"invalid version {args.version!r}: {version_error}")
    triple, expected_suffix = TARGETS[args.target]
    archive = args.archive.resolve()
    if not archive.is_file():
        fail(f"archive does not exist: {archive}")
    if not archive.name.endswith(expected_suffix):
        fail(f"target {args.target} requires an {expected_suffix} archive")
    libc_source = args.libc_source.resolve()
    if not (libc_source / "go.mod").is_file():
        fail(f"c2go-libc module is missing: {libc_source}")

    archive_root = f"c2go-toolchain-{args.version}-{args.target}"
    files = archive_files(archive, archive_root)
    verify_layout(files, args.version, args.target, libc_source)
    with tempfile.TemporaryDirectory(prefix="c2go-sdk-verify-") as temporary:
        package_root = extract_archive(archive, Path(temporary), archive_root)
        verify_build_info(package_root, args.version, args.target)
        verify_pipeline(package_root, triple, args.target, libc_source)
    print(f"C2Go SDK package verified: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
