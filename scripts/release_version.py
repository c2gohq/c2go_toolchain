#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

"""Validate the coordinated C2Go CalVer-in-SemVer release format."""

from __future__ import annotations

import argparse
import datetime as dt
import re


VERSION_PATTERN = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\."
    r"(?P<date>[1-9]\d{3}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01]))\."
    r"(?P<revision>0|[1-9]\d*)"
    r"(?:-rc\.(?P<rc>[1-9]\d*))?$"
)


def validate_release_version(version: object) -> str | None:
    """Return an error string when *version* is not a valid release version."""

    if not isinstance(version, str):
        return "version must be a string"
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        return "expected vMAJOR.YYYYMMDD.REVISION or vMAJOR.YYYYMMDD.REVISION-rc.N"
    try:
        dt.datetime.strptime(match.group("date"), "%Y%m%d")
    except ValueError:
        return f"invalid UTC snapshot date {match.group('date')}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    args = parser.parse_args()

    error = validate_release_version(args.version)
    if error is not None:
        parser.error(f"invalid release version {args.version!r}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
