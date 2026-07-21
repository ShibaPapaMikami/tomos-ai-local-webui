#!/usr/bin/env python3
"""Persistent-data path tests for the signed macOS app bundle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TomosAppDataTests(unittest.TestCase):
    def test_server_uses_application_support_for_all_mutable_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            support_root = Path(temp_dir) / "Library" / "Application Support" / "TOMOS AI"
            environment = os.environ.copy()
            environment["TOMOS_APP_SUPPORT_DIR"] = str(support_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import json, server; print(json.dumps({"
                    "'knowledge': str(server.KNOWLEDGE_DB_PATH), "
                    "'context': str(server.CONTEXT_DB_PATH), "
                    "'contracts': str(server.CONTRACT_DB_PATH), "
                    "'packs': str(server.STUDY_PACK_INSTALL_ROOT), "
                    "'photos': str(server.PERSON_PHOTO_DIR), "
                    "'codegraph': str(server.CODEGRAPH_APP_CACHE_DIR)}))",
                ],
                cwd=ROOT,
                env=environment,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            paths = json.loads(completed.stdout)

        self.assertEqual(paths["knowledge"], str(support_root / ".gemma4-data" / "knowledge" / "index.sqlite"))
        self.assertEqual(paths["context"], str(support_root / ".gemma4-data" / "context" / "context.sqlite"))
        self.assertEqual(paths["contracts"], str(support_root / ".gemma4-data" / "contracts" / "contracts.sqlite"))
        self.assertEqual(paths["packs"], str(support_root / ".gemma4-data" / "study-packs"))
        self.assertEqual(paths["photos"], str(support_root / "data" / "person-photos"))
        self.assertEqual(paths["codegraph"], str(support_root / ".gemma4-data" / "codegraph"))


if __name__ == "__main__":
    unittest.main()
