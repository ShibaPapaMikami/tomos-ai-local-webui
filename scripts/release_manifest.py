from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
RELEASE_VERSION = "0.8.234"
TAG_NAME = "v0.8.234"
PLATFORMS = ("macos", "windows")

ROOT_FIELDS = {
    "schema_version",
    "stage",
    "release_version",
    "platform",
    "tag_name",
    "tag_target_commit",
    "source_tree_sha",
    "source_clean",
    "ci_run",
    "toolchain",
    "runtime",
    "artifact",
    "signing",
    "mac_notary_submission_id",
    "third_party_tested_sha256",
}
RUNTIME_FIELDS = {"source", "version", "size", "sha256", "license"}
ARTIFACT_FIELDS = {"name", "platform", "size", "sha256"}
SIGNING_FIELDS = {"subject", "timestamp"}
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
SEMVER_TOKEN = re.compile(r"(?<![0-9.])v?(\d+\.\d+\.\d+)(?![0-9.])")
SENSITIVE_TOKEN = re.compile(
    r"(?:^|[^a-z0-9])(?:api[\s_:-]*key|access[\s_:-]*key|auth|credential|oauth|"
    r"password|private[\s_:-]*key|secret|token)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)
CREDENTIAL_PREFIX = re.compile(
    r"(?:^|[^a-z0-9])(?:gh[pousr]_|github_pat_|glpat-|xox[baprs]-|xapp-|"
    r"sk-[a-z][a-z0-9_-]{7,}|(?:AKIA|ASIA)[0-9A-Z]{16})",
    re.IGNORECASE,
)


class ContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise ContractError(code)


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail("invalid_type")
    return value


def _exact_fields(value: Mapping[str, object], expected: set[str]) -> None:
    actual = set(value)
    if expected - actual:
        _fail("missing_field")
    if actual - expected:
        _fail("unknown_field")


def _string(value: object, *, public_metadata: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("invalid_type")
    if any(ord(character) < 32 for character in value):
        _fail("invalid_type")
    if public_metadata:
        if SENSITIVE_TOKEN.search(value) or CREDENTIAL_PREFIX.search(value):
            _fail("sensitive_value")
        looks_like_url = "://" in value
        try:
            parsed = urlsplit(value)
        except ValueError:
            _fail("sensitive_value")
        is_public_url = bool(
            looks_like_url and parsed.scheme.lower() == "https" and parsed.netloc
        )
        if looks_like_url and not is_public_url:
            _fail("sensitive_value")
        if is_public_url and (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            _fail("sensitive_value")
        if not is_public_url:
            if (
                value.startswith(("/", "~", "\\"))
                or "/" in value
                or "\\" in value
                or PureWindowsPath(value).is_absolute()
            ):
                _fail("sensitive_value")
    return value


def _sha(value: object, length: int) -> str:
    if not isinstance(value, str):
        _fail("invalid_type")
    pattern = HEX40 if length == 40 else HEX64
    if pattern.fullmatch(value) is None:
        _fail("invalid_sha")
    return value


def _positive_size(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("invalid_type")
    if value <= 0:
        _fail("invalid_size")
    return value


def _artifact_name(value: object) -> str:
    name = _string(value)
    if (
        Path(name).is_absolute()
        or PureWindowsPath(name).is_absolute()
        or "/" in name
        or "\\" in name
        or name in {".", ".."}
    ):
        _fail("unsafe_path")
    return name


def _validate_platform(value: object) -> str:
    if not isinstance(value, str) or value not in PLATFORMS:
        _fail("invalid_platform")
    return value


def _validate_runtime(value: object) -> None:
    runtime = _mapping(value)
    _exact_fields(runtime, RUNTIME_FIELDS)
    _string(runtime["source"], public_metadata=True)
    _string(runtime["version"], public_metadata=True)
    _positive_size(runtime["size"])
    _sha(runtime["sha256"], 64)
    _string(runtime["license"], public_metadata=True)


def _validate_artifact_shape(value: object, platform: str, stage: str) -> None:
    artifact = _mapping(value)
    _exact_fields(artifact, ARTIFACT_FIELDS)
    if stage == "source":
        if any(artifact[field] is not None for field in ARTIFACT_FIELDS):
            _fail("stage_contract")
        return
    if any(artifact[field] is None for field in ("name", "size", "sha256")):
        _fail("stage_contract")
    if artifact["platform"] is None:
        _fail("stage_contract")
    if artifact["platform"] != platform:
        _fail("invalid_platform")
    name = _artifact_name(artifact["name"])
    versions = SEMVER_TOKEN.findall(name)
    if RELEASE_VERSION not in versions or any(
        version != RELEASE_VERSION for version in versions
    ):
        _fail("historical_artifact")
    expected_extension = ".pkg" if platform == "macos" else ".msi"
    if not name.endswith(expected_extension):
        _fail("invalid_extension")
    _positive_size(artifact["size"])
    _sha(artifact["sha256"], 64)


def _validate_signing(value: object, stage: str) -> None:
    signing = _mapping(value)
    _exact_fields(signing, SIGNING_FIELDS)
    if stage == "source":
        if signing["subject"] is not None or signing["timestamp"] is not None:
            _fail("stage_contract")
        return
    if signing["subject"] is None or signing["timestamp"] is None:
        _fail("stage_contract")
    _string(signing["subject"], public_metadata=True)
    _string(signing["timestamp"])


def _validate_stage_fields(manifest: Mapping[str, object], platform: str, stage: str) -> None:
    _validate_artifact_shape(manifest["artifact"], platform, stage)
    _validate_signing(manifest["signing"], stage)
    notary = manifest["mac_notary_submission_id"]
    third_party = manifest["third_party_tested_sha256"]
    if stage == "source":
        if notary is not None or third_party is not None:
            _fail("stage_contract")
        return
    if platform == "macos":
        _string(notary, public_metadata=True)
    elif notary is not None:
        _fail("stage_contract")
    tested_sha = _sha(third_party, 64)
    artifact = _mapping(manifest["artifact"])
    if tested_sha != artifact["sha256"]:
        _fail("artifact_mismatch")


def _has_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    return any(component.is_symlink() for component in (absolute, *absolute.parents))


def _validate_artifact_file(manifest: Mapping[str, object], artifact_root: Path | None) -> None:
    if artifact_root is None:
        _fail("filesystem_required")
    try:
        if _has_symlink_component(artifact_root):
            _fail("symlink")
        if not artifact_root.is_dir():
            _fail("artifact_missing")
        root = artifact_root.resolve(strict=True)
        artifact = _mapping(manifest["artifact"])
        name = _artifact_name(artifact["name"])
        candidate = artifact_root / name
        if candidate.is_symlink():
            _fail("symlink")
        resolved = candidate.resolve(strict=True)
        if resolved.parent != root or not resolved.is_file():
            _fail("unsafe_path")
        size = resolved.stat().st_size
        hasher = hashlib.sha256()
        with resolved.open("rb") as artifact_file:
            for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
    except ContractError:
        raise
    except (OSError, RuntimeError):
        _fail("artifact_missing")
    if size != artifact["size"] or digest != artifact["sha256"]:
        _fail("artifact_mismatch")


def validate_release_manifest(
    raw: Mapping[str, object], *, artifact_root: Path | None = None
) -> dict[str, object]:
    manifest = _mapping(raw)
    _exact_fields(manifest, ROOT_FIELDS)
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        _fail("invalid_type")
    stage = manifest["stage"]
    if stage not in ("source", "final"):
        _fail("invalid_stage")
    if manifest["release_version"] != RELEASE_VERSION or manifest["tag_name"] != TAG_NAME:
        _fail("historical_release")
    platform = _validate_platform(manifest["platform"])
    _sha(manifest["tag_target_commit"], 40)
    _sha(manifest["source_tree_sha"], 40)
    if manifest["source_clean"] is not True:
        if isinstance(manifest["source_clean"], bool):
            _fail("stage_contract")
        _fail("invalid_type")
    _string(manifest["ci_run"], public_metadata=True)
    _string(manifest["toolchain"], public_metadata=True)
    _validate_runtime(manifest["runtime"])
    _validate_stage_fields(manifest, platform, stage)
    if stage == "final":
        _validate_artifact_file(manifest, artifact_root)
    return dict(manifest)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_key")
        result[key] = value
    return result


def load_release_manifest(
    path: Path, *, artifact_root: Path | None = None
) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("invalid_json")
    return validate_release_manifest(_mapping(raw), artifact_root=artifact_root)


def validate_release_set(
    mac_manifest: Mapping[str, object],
    windows_manifest: Mapping[str, object],
    *,
    artifact_root: Path | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    mac_raw = _mapping(mac_manifest)
    windows_raw = _mapping(windows_manifest)
    validated_items = (
        validate_release_manifest(mac_raw, artifact_root=artifact_root),
        validate_release_manifest(windows_raw, artifact_root=artifact_root),
    )
    correlation_fields = (
        "stage",
        "release_version",
        "tag_name",
        "tag_target_commit",
        "source_tree_sha",
    )
    if any(
        validated_items[0][field] != validated_items[1][field]
        for field in correlation_fields
    ):
        _fail("release_set_mismatch")
    if {item["platform"] for item in validated_items} != set(PLATFORMS):
        _fail("release_set_platform")
    validated = {manifest["platform"]: manifest for manifest in validated_items}
    return validated["macos"], validated["windows"]


class _QuietArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        _fail("invalid_arguments")


def _main(argv: list[str]) -> int:
    parser = _QuietArgumentParser(add_help=False)
    parser.add_argument("manifest")
    parser.add_argument("--artifact-root")
    try:
        arguments = parser.parse_args(argv)
        root = Path(arguments.artifact_root) if arguments.artifact_root else None
        load_release_manifest(Path(arguments.manifest), artifact_root=root)
    except ContractError as exc:
        print(exc.code, file=sys.stderr)
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
