#!/usr/bin/env python3
"""Contract tests for the Windows release supply lock."""

from __future__ import annotations

import copy
import ast
from dataclasses import replace
import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator


SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from windows_supply_lock import (  # noqa: E402
    ContractError,
    load_windows_supply_lock,
    main,
    project_python_runtime,
    require_m0_contract,
    validate_windows_supply_lock,
)

FIXED_NOW = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


@contextmanager
def assert_raises_code(expected: str) -> Iterator[None]:
    try:
        yield
    except ContractError as error:
        assert error.code == expected, (error.code, expected)
    else:
        raise AssertionError(f"expected ContractError: {expected}")


def validate_fixture(raw: dict[str, object]):
    return validate_windows_supply_lock(raw, now=FIXED_NOW)


def capture_contract_error(
    expected: str,
    operation: Callable[[], object],
) -> ContractError:
    try:
        operation()
    except ContractError as error:
        assert error.code == expected, (error.code, expected)
        return error
    raise AssertionError(f"expected ContractError: {expected}")


def supply_fixture(name: str, sha256: str) -> dict[str, object]:
    return {
        "source": "fixture-source",
        "version": "1.0.0",
        "artifact_name": name,
        "url": f"https://download.fixture.invalid/{name}",
        "size": 1024,
        "sha256": sha256,
        "license_name": "Fixture License",
        "license_url": "https://license.fixture.invalid/license.txt",
        "license_sha256": "D" * 64,
        "supported_architecture": "x64",
    }


def valid_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "architecture": "x64",
        "certificate": {
            "provider": "fixture-provider",
            "subject": "CN=TOMOS Fixture",
            "issuer": "CN=Fixture Issuer",
            "fingerprint": "A" * 64,
            "key_identity": "fixture-key",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "storage_kind": "fixture-only",
        },
        "timestamp": {
            "rfc3161_url": "https://timestamp.fixture.invalid/rfc3161",
            "digest": "sha256",
        },
        "python_runtime": supply_fixture("python-runtime.zip", "B" * 64),
        "webview2": supply_fixture("webview2-offline.exe", "C" * 64),
    }


class WindowsSupplyLockTest(unittest.TestCase):
    def test_valid_fixture_builds_immutable_contract(self) -> None:
        lock = validate_fixture(valid_fixture())

        self.assertEqual(lock.schema_version, 1)
        self.assertEqual(lock.architecture, "x64")
        self.assertEqual(lock.certificate.provider, "fixture-provider")
        self.assertEqual(lock.timestamp.digest, "sha256")
        self.assertEqual(lock.python_runtime.artifact_name, "python-runtime.zip")
        self.assertEqual(lock.webview2.supported_architecture, "x64")

    def test_supply_lock_rejects_unknown_key(self) -> None:
        raw = valid_fixture()
        raw["unexpected"] = True
        with assert_raises_code("unknown_field"):
            validate_fixture(raw)

    def test_supply_lock_rejects_missing_and_nested_unknown_keys(self) -> None:
        missing = valid_fixture()
        del missing["timestamp"]
        with assert_raises_code("missing_field"):
            validate_fixture(missing)

        nested = valid_fixture()
        certificate = nested["certificate"]
        assert isinstance(certificate, dict)
        certificate["unexpected"] = True
        with assert_raises_code("unknown_field"):
            validate_fixture(nested)

    def test_supply_lock_requires_x64_for_root_and_artifacts(self) -> None:
        root = valid_fixture()
        root["architecture"] = "arm64"
        with assert_raises_code("unsupported_architecture"):
            validate_fixture(root)

        artifact = valid_fixture()
        python_runtime = artifact["python_runtime"]
        assert isinstance(python_runtime, dict)
        python_runtime["supported_architecture"] = "arm64"
        with assert_raises_code("unsupported_architecture"):
            validate_fixture(artifact)

    def test_supply_lock_rejects_invalid_types_and_empty_strings(self) -> None:
        invalid_type = valid_fixture()
        invalid_type["schema_version"] = "1"
        with assert_raises_code("invalid_type"):
            validate_fixture(invalid_type)

        empty = valid_fixture()
        certificate = empty["certificate"]
        assert isinstance(certificate, dict)
        certificate["provider"] = " "
        with assert_raises_code("empty_value"):
            validate_fixture(empty)

        nested_type = valid_fixture()
        nested_type["webview2"] = []
        with assert_raises_code("invalid_type"):
            validate_fixture(nested_type)

    def test_supply_lock_requires_https_urls(self) -> None:
        for section, key in (
            ("timestamp", "rfc3161_url"),
            ("python_runtime", "url"),
            ("python_runtime", "license_url"),
        ):
            with self.subTest(section=section, key=key):
                raw = valid_fixture()
                nested = raw[section]
                assert isinstance(nested, dict)
                nested[key] = "http://fixture.invalid/file"
                with assert_raises_code("insecure_url"):
                    validate_fixture(raw)

        malformed = valid_fixture()
        timestamp = malformed["timestamp"]
        assert isinstance(timestamp, dict)
        timestamp["rfc3161_url"] = "https://[invalid"
        with assert_raises_code("insecure_url"):
            validate_fixture(malformed)

    def test_supply_lock_requires_positive_sizes_and_sha256_values(self) -> None:
        invalid_size = valid_fixture()
        python_runtime = invalid_size["python_runtime"]
        assert isinstance(python_runtime, dict)
        python_runtime["size"] = 0
        with assert_raises_code("invalid_size"):
            validate_fixture(invalid_size)

        for section, key in (
            ("certificate", "fingerprint"),
            ("python_runtime", "sha256"),
            ("python_runtime", "license_sha256"),
        ):
            with self.subTest(section=section, key=key):
                raw = valid_fixture()
                nested = raw[section]
                assert isinstance(nested, dict)
                nested[key] = "not-a-sha256"
                with assert_raises_code("invalid_sha256"):
                    validate_fixture(raw)

        sha1_thumbprint = valid_fixture()
        certificate = sha1_thumbprint["certificate"]
        assert isinstance(certificate, dict)
        certificate["fingerprint"] = "A" * 40
        with assert_raises_code("invalid_sha256"):
            validate_fixture(sha1_thumbprint)

    def test_key_identity_rejects_secret_material_and_certificate_paths(self) -> None:
        forbidden_values = (
            "token=fixture-token-value",
            "api_key: fixture-secret",
            "credential fixture-value",
            "pass-word=fixture-value",
            "auth: fixture-value",
            "oauth_code=fixture-value",
            "private-key fixture-value",
            "-----BEGIN PRIVATE KEY-----",
            "../signing-key",
            "certificates/signing-key",
            r"C:\certificates\tomos-signing.pfx",
            "/Users/fixture/certificates/tomos-signing.p12",
            "file:///fixture/tomos-signing.pem",
        )
        for value in forbidden_values:
            with self.subTest(value=value):
                raw = valid_fixture()
                certificate = raw["certificate"]
                assert isinstance(certificate, dict)
                certificate["key_identity"] = value
                with assert_raises_code("sensitive_value"):
                    validate_fixture(raw)

    def test_storage_kind_rejects_paths_and_secret_material(self) -> None:
        for value in (
            r"C:\certificates",
            "/Users/fixture/certificates",
            "../certificate-store",
            "secret=fixture-secret",
            "cred-ential: fixture-value",
            "api key fixture-value",
            "pass_word=fixture-value",
            "oauth-code fixture-value",
        ):
            with self.subTest(value=value):
                raw = valid_fixture()
                certificate = raw["certificate"]
                assert isinstance(certificate, dict)
                certificate["storage_kind"] = value
                with assert_raises_code("sensitive_value"):
                    validate_fixture(raw)

    def test_artifact_urls_reject_credential_query_parameters(self) -> None:
        for suffix in (
            "?token=fixture-secret",
            "?api_key=fixture-secret",
            "?X-Amz-Signature=fixture-secret",
            "?AWSAccessKeyId=fixture-secret",
            "?authorization=fixture-secret",
            "?auth=fixture-secret",
            "?oauth_code=fixture-secret",
            "?download=1",
            "?",
            "#sha256",
            "#",
        ):
            with self.subTest(suffix=suffix):
                raw = valid_fixture()
                python_runtime = raw["python_runtime"]
                assert isinstance(python_runtime, dict)
                python_runtime["url"] = (
                    f"https://download.fixture.invalid/python-runtime.zip{suffix}"
                )
                with assert_raises_code("sensitive_value"):
                    validate_fixture(raw)

    def test_supply_lock_rejects_unresolved_readback_values(self) -> None:
        for value in (
            "TBD",
            "TBC",
            "N/A",
            "N / A",
            "unknown",
            "placeholder",
            "pending readback",
            "awaiting_readback",
            "not-approved",
            "未確認",
        ):
            with self.subTest(value=value):
                raw = valid_fixture()
                python_runtime = raw["python_runtime"]
                assert isinstance(python_runtime, dict)
                python_runtime["source"] = value
                with assert_raises_code("unresolved_value"):
                    validate_fixture(raw)

    def test_certificate_validity_requires_rfc3339_utc(self) -> None:
        for value in (
            "2026-01-01",
            "2026-01-01T00:00:00+09:00",
            "2026-02-30T00:00:00Z",
        ):
            with self.subTest(value=value):
                raw = valid_fixture()
                certificate = raw["certificate"]
                assert isinstance(certificate, dict)
                certificate["valid_from"] = value
                with assert_raises_code("invalid_datetime"):
                    validate_fixture(raw)

    def test_certificate_validity_window_must_be_ordered(self) -> None:
        for valid_from, valid_until in (
            ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            ("2027-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        ):
            with self.subTest(valid_from=valid_from, valid_until=valid_until):
                raw = valid_fixture()
                certificate = raw["certificate"]
                assert isinstance(certificate, dict)
                certificate["valid_from"] = valid_from
                certificate["valid_until"] = valid_until
                with assert_raises_code("invalid_validity_window"):
                    validate_fixture(raw)

    def test_certificate_must_be_current_at_explicit_validation_time(self) -> None:
        raw = valid_fixture()
        with assert_raises_code("certificate_not_current"):
            validate_windows_supply_lock(
                raw,
                now=datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            )
        with assert_raises_code("certificate_not_current"):
            validate_windows_supply_lock(
                raw,
                now=datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )

    def test_supply_lock_requires_sha256_timestamp_digest(self) -> None:
        raw = valid_fixture()
        timestamp = raw["timestamp"]
        assert isinstance(timestamp, dict)
        timestamp["digest"] = "sha1"
        with assert_raises_code("unsupported_digest"):
            validate_fixture(raw)

    def test_loader_rejects_duplicate_json_keys(self) -> None:
        raw = """{
          "schema_version": 1,
          "schema_version": 1
        }"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "lock.json"
            path.write_text(raw, encoding="utf-8")
            with assert_raises_code("duplicate_key"):
                load_windows_supply_lock(path)

    def test_validation_does_not_mutate_input(self) -> None:
        raw = valid_fixture()
        before = copy.deepcopy(raw)
        validate_fixture(raw)
        self.assertEqual(raw, before)

    def test_m0_contract_matches_approved_release_manifest_schema(self) -> None:
        class PlatformTuple(tuple):
            pass

        contract = require_m0_contract()
        self.assertEqual(contract.SCHEMA_VERSION, 1)
        self.assertIn("windows", contract.PLATFORMS)
        self.assertEqual(
            contract.RUNTIME_FIELDS,
            {"source", "version", "size", "sha256", "license"},
        )

        with assert_raises_code("m0_contract_unavailable"):
            require_m0_contract(object())

        expected = {
            "SCHEMA_VERSION": 1,
            "PLATFORMS": ("macos", "windows"),
            "RUNTIME_FIELDS": {"source", "version", "size", "sha256", "license"},
        }
        for key, value in (
            ("SCHEMA_VERSION", 2),
            ("SCHEMA_VERSION", True),
            ("PLATFORMS", ("macos",)),
            ("PLATFORMS", ("windows", "linux")),
            ("PLATFORMS", ("macos", "windows", "linux")),
            ("PLATFORMS", {"windows"}),
            ("PLATFORMS", PlatformTuple(("macos", "windows"))),
            ("PLATFORMS", None),
            ("RUNTIME_FIELDS", {"source", "version", "size", "sha256"}),
        ):
            with self.subTest(key=key):
                mismatch = dict(expected)
                mismatch[key] = value
                with assert_raises_code("m0_contract_mismatch"):
                    require_m0_contract(SimpleNamespace(**mismatch))

    def test_python_runtime_projection_contains_only_m0_runtime_fields(self) -> None:
        lock = validate_fixture(valid_fixture())
        projection = project_python_runtime(lock)

        self.assertEqual(
            projection,
            {
                "source": "https://download.fixture.invalid/python-runtime.zip",
                "version": "1.0.0",
                "size": 1024,
                "sha256": "b" * 64,
                "license": "Fixture License",
            },
        )
        self.assertEqual(
            set(projection),
            {"source", "version", "size", "sha256", "license"},
        )

    def test_python_runtime_projection_rejects_private_metadata(self) -> None:
        lock = validate_fixture(valid_fixture())
        cases = (
            ("url", "https://user:password@fixture.invalid/runtime", "sensitive_value"),
            ("url", "https:example.invalid", "sensitive_value"),
            ("url", "ftp:example.invalid", "sensitive_value"),
            ("url", "approved-runtime-catalog", "sensitive_value"),
            ("url", "https://fixture.invalid/runtime?", "sensitive_value"),
            ("url", "https://fixture.invalid/runtime#", "sensitive_value"),
            ("version", "token: fixture-secret", "sensitive_value"),
            (
                "license_name",
                "/Users/customer/private/license.txt",
                "sensitive_value",
            ),
            ("size", True, "invalid_type"),
            ("size", 0, "invalid_size"),
            ("sha256", "not-a-sha256", "invalid_sha256"),
        )
        for field, value, expected_code in cases:
            with self.subTest(field=field):
                runtime = replace(lock.python_runtime, **{field: value})
                changed = replace(lock, python_runtime=runtime)
                error = capture_contract_error(
                    expected_code,
                    lambda: project_python_runtime(changed),
                )
                self.assertNotIn(str(value), str(error))

    def test_cli_stops_for_external_readback_after_m0_contract_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "windows-supply-lock.json"
            evidence_path = root / "windows-supply-evidence.md"
            upgrade_path = root / "upgrade-code-evidence.md"
            lock_path.write_text(json.dumps(valid_fixture()), encoding="utf-8")
            evidence_path.write_text("approved synthetic evidence\n", encoding="utf-8")
            upgrade_path.write_text("approved synthetic upgrade evidence\n", encoding="utf-8")

            with assert_raises_code("external_readback_required"):
                main(
                    [
                        "--lock",
                        str(lock_path),
                        "--evidence",
                        str(evidence_path),
                        "--upgrade-code-evidence",
                        str(upgrade_path),
                    ],
                    now=FIXED_NOW,
                )

    def test_cli_never_treats_arbitrary_evidence_as_approval(self) -> None:
        module_path = SCRIPTS_DIR / "windows_supply_lock.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "windows-supply-lock.json"
            evidence_path = root / "windows-supply-evidence.md"
            upgrade_path = root / "upgrade-code-evidence.md"
            raw = valid_fixture()
            certificate = raw["certificate"]
            assert isinstance(certificate, dict)
            certificate["valid_until"] = "2099-01-01T00:00:00Z"
            lock_path.write_text(json.dumps(raw), encoding="utf-8")
            evidence_path.write_text("arbitrary nonempty text\n", encoding="utf-8")
            upgrade_path.write_text("not an approval record\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(module_path),
                    "--lock",
                    str(lock_path),
                    "--evidence",
                    str(evidence_path),
                    "--upgrade-code-evidence",
                    str(upgrade_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "external_readback_required\n")

    def test_module_cli_consumes_sibling_m0_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "windows-supply-lock.json"
            evidence_path = root / "windows-supply-evidence.md"
            upgrade_path = root / "upgrade-code-evidence.md"
            raw = valid_fixture()
            certificate = raw["certificate"]
            assert isinstance(certificate, dict)
            certificate["valid_until"] = "2099-01-01T00:00:00Z"
            lock_path.write_text(json.dumps(raw), encoding="utf-8")
            evidence_path.write_text("synthetic evidence\n", encoding="utf-8")
            upgrade_path.write_text("synthetic upgrade evidence\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.windows_supply_lock",
                    "--lock",
                    str(lock_path),
                    "--evidence",
                    str(evidence_path),
                    "--upgrade-code-evidence",
                    str(upgrade_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "external_readback_required\n")

    def test_cli_fails_closed_when_readback_evidence_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "windows-supply-lock.json"
            evidence_path = root / "windows-supply-evidence.md"
            upgrade_path = root / "upgrade-code-evidence.md"
            lock_path.write_text(json.dumps(valid_fixture()), encoding="utf-8")
            evidence_path.write_text("approved synthetic evidence\n", encoding="utf-8")

            with assert_raises_code("missing_evidence"):
                main(
                    [
                        "--lock",
                        str(lock_path),
                        "--evidence",
                        str(evidence_path),
                        "--upgrade-code-evidence",
                        str(upgrade_path),
                    ],
                    now=FIXED_NOW,
                )

    def test_file_read_errors_do_not_expose_input_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_lock = root / "customer-secret-lock.json"
            error = capture_contract_error(
                "missing_lock",
                lambda: load_windows_supply_lock(missing_lock, now=FIXED_NOW),
            )
            self.assertEqual(str(error), "cannot read supply lock")
            self.assertNotIn(str(missing_lock), str(error))

            invalid_lock = root / "customer-secret-invalid.json"
            invalid_lock.write_text("{", encoding="utf-8")
            error = capture_contract_error(
                "invalid_json",
                lambda: load_windows_supply_lock(invalid_lock, now=FIXED_NOW),
            )
            self.assertEqual(str(error), "invalid supply lock JSON")
            self.assertNotIn(str(invalid_lock), str(error))

            valid_lock = root / "windows-supply-lock.json"
            evidence = root / "windows-supply-evidence.md"
            missing_upgrade = root / "customer-secret-upgrade-evidence.md"
            valid_lock.write_text(json.dumps(valid_fixture()), encoding="utf-8")
            evidence.write_text("approved synthetic evidence\n", encoding="utf-8")
            error = capture_contract_error(
                "missing_evidence",
                lambda: main(
                    [
                        "--lock",
                        str(valid_lock),
                        "--evidence",
                        str(evidence),
                        "--upgrade-code-evidence",
                        str(missing_upgrade),
                    ],
                    now=FIXED_NOW,
                ),
            )
            self.assertEqual(str(error), "cannot read upgrade code evidence")
            self.assertNotIn(str(missing_upgrade), str(error))

    def test_cli_stderr_contains_only_fixed_contract_error_code(self) -> None:
        module_path = SCRIPTS_DIR / "windows_supply_lock.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence.md"
            upgrade = root / "upgrade.md"
            evidence.write_text("synthetic evidence\n", encoding="utf-8")
            upgrade.write_text("synthetic upgrade evidence\n", encoding="utf-8")

            missing_lock = root / "customer-secret-lock.json"
            invalid_lock = root / "customer-secret-invalid.json"
            invalid_utf8_lock = root / "customer-secret-invalid-utf8.json"
            invalid_lock.write_text("{", encoding="utf-8")
            invalid_utf8_lock.write_bytes(b"\xff\xfe\xfa")

            for lock_path, expected_code in (
                (missing_lock, "missing_lock"),
                (invalid_lock, "invalid_json"),
                (invalid_utf8_lock, "invalid_json"),
            ):
                with self.subTest(expected_code=expected_code):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(module_path),
                            "--lock",
                            str(lock_path),
                            "--evidence",
                            str(evidence),
                            "--upgrade-code-evidence",
                            str(upgrade),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, f"{expected_code}\n")
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertNotIn("UnicodeDecodeError", result.stderr)
                    self.assertNotIn(str(lock_path), result.stderr)
                    self.assertNotIn("windows_supply_lock.py", result.stderr)

    def test_cli_argument_errors_do_not_expose_secret_or_paths(self) -> None:
        module_path = SCRIPTS_DIR / "windows_supply_lock.py"
        secret_path = "/Users/customer/private/api-token.txt"
        result = subprocess.run(
            [sys.executable, str(module_path), "--unexpected", secret_path],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "invalid_arguments\n")
        self.assertNotIn(secret_path, result.stderr)
        self.assertNotIn("usage:", result.stderr)
        self.assertNotIn("windows_supply_lock.py", result.stderr)

    def test_cli_invalid_utf8_evidence_uses_fixed_error_only(self) -> None:
        module_path = SCRIPTS_DIR / "windows_supply_lock.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "windows-supply-lock.json"
            raw = valid_fixture()
            certificate = raw["certificate"]
            assert isinstance(certificate, dict)
            certificate["valid_until"] = "2099-01-01T00:00:00Z"
            lock_path.write_text(json.dumps(raw), encoding="utf-8")

            for invalid_name in ("private-evidence.md", "private-upgrade.md"):
                with self.subTest(invalid_name=invalid_name):
                    evidence = root / "evidence.md"
                    upgrade = root / "upgrade.md"
                    evidence.write_text("synthetic evidence\n", encoding="utf-8")
                    upgrade.write_text("synthetic upgrade evidence\n", encoding="utf-8")
                    invalid_path = root / invalid_name
                    invalid_path.write_bytes(b"\xff\xfe\xfa")
                    if "upgrade" in invalid_name:
                        upgrade = invalid_path
                    else:
                        evidence = invalid_path

                    result = subprocess.run(
                        [
                            sys.executable,
                            str(module_path),
                            "--lock",
                            str(lock_path),
                            "--evidence",
                            str(evidence),
                            "--upgrade-code-evidence",
                            str(upgrade),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "missing_evidence\n")
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertNotIn("UnicodeDecodeError", result.stderr)
                    self.assertNotIn(str(invalid_path), result.stderr)
                    self.assertNotIn("windows_supply_lock.py", result.stderr)

    def test_task1_module_has_no_download_or_process_execution_boundary(self) -> None:
        module_path = SCRIPTS_DIR / "windows_supply_lock.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_modules: set[str] = set()
        function_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_names.add(node.name)

        self.assertTrue(
            imported_modules.isdisjoint(
                {"requests", "urllib.request", "http.client", "subprocess", "socket"}
            )
        )
        self.assertFalse(any(name.startswith(("download", "fetch")) for name in function_names))


if __name__ == "__main__":
    unittest.main()
