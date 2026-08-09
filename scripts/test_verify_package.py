#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests for installed SDK verification."""

import importlib.util
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "verify_package", SCRIPTS / "verify-package.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load verify-package.py")
verify_package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_package)


class VerifyHeadersTest(TestCase):
    def test_windows_skips_unavailable_root_and_managed_ftw_headers(self) -> None:
        headers = {"ftw.h", "c2go/mlib/ftw.h", "stdio.h"}

        with patch.object(verify_package, "run") as run:
            verify_package.verify_headers(
                Path("c2go-clang.exe"),
                "x86_64-pc-windows-goabi",
                "windows-amd64",
                headers,
            )

        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["stdin"], "#include <stdio.h>\n")

    def test_non_windows_still_checks_every_header(self) -> None:
        headers = {"ftw.h", "c2go/mlib/ftw.h", "stdio.h"}

        with patch.object(verify_package, "run") as run:
            verify_package.verify_headers(
                Path("c2go-clang"),
                "x86_64-unknown-linux-goabi",
                "linux-amd64",
                headers,
            )

        self.assertEqual(run.call_count, len(headers))
