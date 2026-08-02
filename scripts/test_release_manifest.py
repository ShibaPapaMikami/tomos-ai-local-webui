from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from release_manifest import (
    ContractError,
    load_release_manifest,
    validate_release_manifest,
    validate_release_set,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/release_manifest.py"
COMMIT = "a" * 40
TREE = "b" * 40
RUNTIME_SHA = "c" * 64


def expect_error(code: str, function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except ContractError as exc:
        assert exc.code == code, (exc.code, code)
        assert str(exc) == code
    else:
        raise AssertionError(f"expected {code}")


def source_manifest(platform: str = "macos") -> dict[str, object]:
    return {
        "schema_version": 1,
        "stage": "source",
        "release_version": "0.8.234",
        "platform": platform,
        "tag_name": "v0.8.234",
        "tag_target_commit": COMMIT,
        "source_tree_sha": TREE,
        "source_clean": True,
        "ci_run": "github-actions-run-123",
        "toolchain": "python-3.14",
        "runtime": {
            "source": "approved-runtime-catalog",
            "version": "3.14.0",
            "size": 1024,
            "sha256": RUNTIME_SHA,
            "license": "PSF-2.0",
        },
        "artifact": {
            "name": None,
            "platform": None,
            "size": None,
            "sha256": None,
        },
        "signing": {"subject": None, "timestamp": None},
        "mac_notary_submission_id": None,
        "third_party_tested_sha256": None,
    }


def final_manifest(root: Path, platform: str) -> dict[str, object]:
    extension = ".pkg" if platform == "macos" else ".msi"
    name = f"TOMOS_AI-v0.8.234-{platform}{extension}"
    payload = f"fixture-{platform}".encode()
    (root / name).write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = source_manifest(platform)
    manifest.update(
        {
            "stage": "final",
            "artifact": {
                "name": name,
                "platform": platform,
                "size": len(payload),
                "sha256": digest,
            },
            "signing": {
                "subject": f"fixture-{platform}-signer",
                "timestamp": "2026-08-02T00:00:00Z",
            },
            "mac_notary_submission_id": (
                "fixture-notary-submission" if platform == "macos" else None
            ),
            "third_party_tested_sha256": digest,
        }
    )
    return manifest


def test_source_and_final_fixtures() -> None:
    assert validate_release_manifest(source_manifest())["stage"] == "source"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        manifest = final_manifest(root, "macos")
        assert validate_release_manifest(manifest, artifact_root=root)["stage"] == "final"


def test_exact_fields_types_hashes_and_sizes() -> None:
    unknown = source_manifest()
    unknown["extra"] = "value"
    expect_error("unknown_field", validate_release_manifest, unknown)

    missing = source_manifest()
    del missing["ci_run"]
    expect_error("missing_field", validate_release_manifest, missing)

    nested = source_manifest()
    nested["runtime"]["extra"] = "value"  # type: ignore[index]
    expect_error("unknown_field", validate_release_manifest, nested)

    wrong_type = source_manifest()
    wrong_type["source_clean"] = 1
    expect_error("invalid_type", validate_release_manifest, wrong_type)

    wrong_schema_type = source_manifest()
    wrong_schema_type["schema_version"] = 1.0
    expect_error("invalid_type", validate_release_manifest, wrong_schema_type)

    bad_sha = source_manifest()
    bad_sha["source_tree_sha"] = "b" * 63
    expect_error("invalid_sha", validate_release_manifest, bad_sha)

    bad_size = source_manifest()
    bad_size["runtime"]["size"] = 0  # type: ignore[index]
    expect_error("invalid_size", validate_release_manifest, bad_size)


def test_duplicate_json_key_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        expect_error("duplicate_key", load_release_manifest, path)


def test_stage_contract_and_current_release_are_fixed() -> None:
    final_without_root = source_manifest()
    final_without_root["stage"] = "final"
    expect_error("stage_contract", validate_release_manifest, final_without_root)

    source_with_artifact = source_manifest()
    source_with_artifact["artifact"]["name"] = "candidate.pkg"  # type: ignore[index]
    expect_error("stage_contract", validate_release_manifest, source_with_artifact)

    source_with_platform = source_manifest()
    source_with_platform["artifact"]["platform"] = "macos"  # type: ignore[index]
    expect_error("stage_contract", validate_release_manifest, source_with_platform)

    historical = source_manifest()
    historical["release_version"] = "0.8.233"
    historical["tag_name"] = "v0.8.233"
    expect_error("historical_release", validate_release_manifest, historical)

    wrong_tag = source_manifest()
    wrong_tag["tag_name"] = "v0.8.235"
    expect_error("historical_release", validate_release_manifest, wrong_tag)


def test_public_metadata_rejects_secrets_and_paths() -> None:
    for field, value in (
        ("ci_run", "api_key=fixture-secret"),
        ("ci_run", "ghp_0123456789abcdefghijklmnopqrstuvwxyz"),
        ("ci_run", "sk-svcacct-0123456789abcdefghijklmnopqrstuvwxyz"),
        ("ci_run", "ASIAABCDEFGHIJKLMNOP"),
        ("ci_run", "xapp-1-A0123456789-0123456789-abcdef"),
        ("ci_run", "/Users/example/private/run.json"),
        ("ci_run", "../private/run.json"),
        ("toolchain", "oauth-token fixture"),
        ("toolchain", "C:\\secrets\\toolchain.txt"),
    ):
        manifest = source_manifest()
        manifest[field] = value
        expect_error("sensitive_value", validate_release_manifest, manifest)


def test_runtime_public_metadata_rejects_secrets_and_paths() -> None:
    public_url = source_manifest()
    public_url["runtime"]["source"] = "https://downloads.example.invalid/runtime"  # type: ignore[index]
    assert validate_release_manifest(public_url)["stage"] == "source"

    for field, value in (
        ("source", "https://user:password@example.invalid/runtime"),
        ("source", "http://downloads.example.invalid/runtime"),
        ("source", "ftp://downloads.example.invalid/runtime"),
        ("source", "https://[bad"),
        ("source", "token=fixture-value"),
        ("version", "/Users/example/private/version.txt"),
        ("version", "C:\\private\\version.txt"),
        ("license", "api key fixture-value"),
        ("license", "../private/license.txt"),
    ):
        manifest = source_manifest()
        manifest["runtime"][field] = value  # type: ignore[index]
        expect_error("sensitive_value", validate_release_manifest, manifest)


def test_malformed_runtime_url_cli_error_is_fixed_and_quiet() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory).resolve() / "private-runtime-manifest.json"
        manifest = source_manifest()
        manifest["runtime"]["source"] = "https://[bad"  # type: ignore[index]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(MODULE), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert result.stderr.strip() == "sensitive_value"
        assert str(path) not in result.stderr
        assert "Traceback" not in result.stderr


def test_artifact_path_and_platform_rules() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        manifest = final_manifest(root, "macos")
        manifest["artifact"]["name"] = "../candidate.pkg"  # type: ignore[index]
        expect_error("unsafe_path", validate_release_manifest, manifest, artifact_root=root)

        manifest = final_manifest(root, "macos")
        manifest["artifact"]["name"] = "/tmp/candidate.pkg"  # type: ignore[index]
        expect_error("unsafe_path", validate_release_manifest, manifest, artifact_root=root)

        manifest = final_manifest(root, "macos")
        manifest["artifact"]["platform"] = "windows"  # type: ignore[index]
        expect_error("invalid_platform", validate_release_manifest, manifest, artifact_root=root)

        manifest = final_manifest(root, "macos")
        manifest["artifact"]["name"] = "TOMOS_AI-v0.8.234-macos.msi"  # type: ignore[index]
        expect_error("invalid_extension", validate_release_manifest, manifest, artifact_root=root)

        manifest = final_manifest(root, "macos")
        current_name = manifest["artifact"]["name"]  # type: ignore[index]
        historical_name = str(current_name).replace("0.8.234", "0.8.233")
        (root / historical_name).write_bytes((root / str(current_name)).read_bytes())
        manifest["artifact"]["name"] = historical_name  # type: ignore[index]
        expect_error(
            "historical_artifact",
            validate_release_manifest,
            manifest,
            artifact_root=root,
        )

        manifest = final_manifest(root, "macos")
        current_name = manifest["artifact"]["name"]  # type: ignore[index]
        mixed_name = "TOMOS_AI-v0.8.233-copy-v0.8.234-macos.pkg"
        (root / mixed_name).write_bytes((root / str(current_name)).read_bytes())
        manifest["artifact"]["name"] = mixed_name  # type: ignore[index]
        expect_error(
            "historical_artifact",
            validate_release_manifest,
            manifest,
            artifact_root=root,
        )


def test_symlink_and_filesystem_mismatch_are_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        target = root / "target.pkg"
        target.write_bytes(b"fixture")
        link = root / "TOMOS_AI-v0.8.234-linked.pkg"
        link.symlink_to(target)
        digest = hashlib.sha256(b"fixture").hexdigest()
        manifest = final_manifest(root, "macos")
        manifest["artifact"] = {
            "name": link.name,
            "platform": "macos",
            "size": 7,
            "sha256": digest,
        }
        manifest["third_party_tested_sha256"] = digest
        expect_error("symlink", validate_release_manifest, manifest, artifact_root=root)

        manifest = final_manifest(root, "windows")
        manifest["artifact"]["size"] = 999  # type: ignore[index]
        expect_error("artifact_mismatch", validate_release_manifest, manifest, artifact_root=root)


def test_artifact_root_parent_symlink_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory).resolve()
        real_parent = base / "real-parent"
        real_parent.mkdir()
        linked_parent = base / "linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        root = linked_parent / "artifacts"
        root.mkdir()
        manifest = final_manifest(root, "macos")
        expect_error("symlink", validate_release_manifest, manifest, artifact_root=root)


def test_release_set_requires_matching_mac_and_windows() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        mac = final_manifest(root, "macos")
        windows = final_manifest(root, "windows")
        validated = validate_release_set(mac, windows, artifact_root=root)
        assert [item["platform"] for item in validated] == ["macos", "windows"]

        expect_error(
            "release_set_platform",
            validate_release_set,
            mac,
            mac,
            artifact_root=root,
        )

        for field in ("release_version", "tag_name", "tag_target_commit", "source_tree_sha"):
            changed = json.loads(json.dumps(windows))
            changed[field] = "d" * 40 if field.endswith(("commit", "sha")) else "different"
            expected = (
                "historical_release"
                if field in {"release_version", "tag_name"}
                else "release_set_mismatch"
            )
            expect_error(
                expected,
                validate_release_set,
                mac,
                changed,
                artifact_root=root,
            )

        changed = json.loads(json.dumps(windows))
        changed["third_party_tested_sha256"] = "d" * 64
        expect_error(
            "artifact_mismatch",
            validate_release_set,
            mac,
            changed,
            artifact_root=root,
        )

        mixed_stage = source_manifest("windows")
        expect_error(
            "release_set_mismatch",
            validate_release_set,
            mac,
            mixed_stage,
            artifact_root=root,
        )


def test_release_set_rejects_non_manifest_input_with_fixed_code() -> None:
    expect_error(
        "invalid_type",
        validate_release_set,
        None,
        source_manifest("windows"),
    )


def test_source_validation_never_reads_artifact_filesystem() -> None:
    unavailable = Path("/definitely/not/an/artifact/root")
    assert validate_release_manifest(source_manifest(), artifact_root=unavailable)["stage"] == "source"


def test_only_standard_library_imports() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    allowed = set(sys.stdlib_module_names) | {"__future__"}
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported <= allowed, imported - allowed


def test_cli_reports_fixed_error_without_path_or_traceback() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "private-manifest.json"
        path.write_text("not-json", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(MODULE), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert result.stderr.strip() == "invalid_json"
        assert str(path) not in result.stderr
        assert "Traceback" not in result.stderr

        path.write_bytes(b"\xff\xfe")
        result = subprocess.run(
            [sys.executable, str(MODULE), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert result.stderr.strip() == "invalid_json"
        assert "UnicodeDecodeError" not in result.stderr


def test_cli_argument_error_is_fixed_and_quiet() -> None:
    result = subprocess.run(
        [sys.executable, str(MODULE), "--unexpected"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert result.stderr.strip() == "invalid_arguments"
    assert "usage:" not in result.stderr
    assert "Traceback" not in result.stderr


def main() -> None:
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"release manifest tests passed ({len(tests)})")


if __name__ == "__main__":
    main()
