#!/usr/bin/env python3
"""Validate the approved, local-only Windows release supply lock."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit


REQUIRED_KEYS = {
    "schema_version",
    "architecture",
    "certificate",
    "timestamp",
    "python_runtime",
    "webview2",
}

CERTIFICATE_KEYS = {
    "provider",
    "subject",
    "issuer",
    "fingerprint",
    "key_identity",
    "valid_from",
    "valid_until",
    "storage_kind",
}

TIMESTAMP_KEYS = {
    "rfc3161_url",
    "digest",
}

SUPPLY_ARTIFACT_KEYS = {
    "source",
    "version",
    "artifact_name",
    "url",
    "size",
    "sha256",
    "license_name",
    "license_url",
    "license_sha256",
    "supported_architecture",
}

_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
_RFC3339_UTC_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"
)
_WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"^[a-zA-Z]:[\\/]")
_UNRESOLVED_TOKENS = {
    "tbd",
    "tbc",
    "todo",
    "unknown",
    "unconfirmed",
    "placeholder",
    "未定",
    "未確認",
    "未確定",
}
_UNRESOLVED_PHRASES = {
    "awaiting readback",
    "not approved",
    "not confirmed",
    "pending readback",
}
_UNRESOLVED_COMPACT = {
    "awaitingreadback",
    "notapproved",
    "notconfirmed",
    "pendingreadback",
}
_PRIVATE_KEY_SUFFIXES = (".pfx", ".p12", ".pem", ".key")
_SENSITIVE_IDENTIFIER_TERMS = {
    "apikey",
    "credential",
    "oauth",
    "password",
    "privatekey",
    "auth",
    "authorization",
    "secret",
    "token",
}
_CREDENTIAL_PREFIX_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:gh[pousr]_|github_pat_|glpat-|xox[baprs]-|xapp-|"
    r"sk-[a-z][a-z0-9_-]{7,}|(?:AKIA|ASIA)[0-9A-Z]{16})",
    re.IGNORECASE,
)


class ContractError(Exception):
    """Stable error-code boundary for Windows supply validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class QuietArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ContractError("invalid_arguments", "invalid CLI arguments")


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("invalid_type", f"{field} must be an object")
    return value


def _require_exact_keys(
    raw: Mapping[str, object],
    expected: set[str],
    field: str,
) -> None:
    actual = set(raw)
    missing = expected - actual
    if missing:
        raise ContractError(
            "missing_field",
            f"{field} is missing: {', '.join(sorted(missing))}",
        )
    unknown = actual - expected
    if unknown:
        raise ContractError(
            "unknown_field",
            f"{field} has unknown fields: {', '.join(sorted(map(str, unknown)))}",
        )


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ContractError("invalid_type", f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ContractError("empty_value", f"{field} must not be empty")
    words = _normalized_words(normalized)
    phrase = " ".join(words)
    compact = "".join(words)
    if (
        any(word in _UNRESOLVED_TOKENS for word in words)
        or any(marker in phrase for marker in _UNRESOLVED_PHRASES)
        or any(marker in compact for marker in _UNRESOLVED_COMPACT)
        or compact in {"na", "tbc", "tbd"}
    ):
        raise ContractError("unresolved_value", f"{field} is not approved")
    return normalized


def _require_sha256(value: object, field: str) -> str:
    digest = _require_text(value, field)
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise ContractError("invalid_sha256", f"{field} must be a 64-digit SHA-256")
    return digest.upper()


def _require_https_url(value: object, field: str) -> str:
    url = _require_text(value, field)
    if "?" in url or "#" in url:
        raise ContractError(
            "sensitive_value",
            f"{field} must be a stable HTTPS URL without query or fragment",
        )
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise ContractError("insecure_url", f"{field} must be an HTTPS URL") from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ContractError("insecure_url", f"{field} must be an HTTPS URL")
    return url


def _require_architecture(value: object, field: str) -> str:
    architecture = _require_text(value, field)
    if architecture != "x64":
        raise ContractError("unsupported_architecture", f"{field} must be x64")
    return architecture


def _require_positive_size(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError("invalid_type", f"{field} must be an integer")
    if value <= 0:
        raise ContractError("invalid_size", f"{field} must be positive")
    return value


def _require_rfc3339_utc(value: object, field: str) -> tuple[str, datetime]:
    timestamp = _require_text(value, field)
    if _RFC3339_UTC_PATTERN.fullmatch(timestamp) is None:
        raise ContractError("invalid_datetime", f"{field} must be RFC 3339 UTC")
    try:
        parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except ValueError as error:
        raise ContractError("invalid_datetime", f"{field} must be RFC 3339 UTC") from error
    return timestamp, parsed


def _validation_time(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ContractError("invalid_datetime", "validation time must be timezone-aware")
    return now.astimezone(timezone.utc)


def _normalized_compact(value: str) -> str:
    return "".join(_normalized_words(value))


def _normalized_words(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    tokenized = "".join(
        character if character.isalnum() else " "
        for character in normalized
    )
    return tokenized.split()


def _require_public_identifier(value: object, field: str) -> str:
    identity = _require_text(value, field)
    folded = identity.casefold()
    compact = _normalized_compact(identity)
    path_like = (
        identity.startswith(("/", "~"))
        or folded.startswith("file:")
        or _WINDOWS_ABSOLUTE_PATH_PATTERN.match(identity) is not None
        or "/" in identity
        or "\\" in identity
        or folded.endswith(_PRIVATE_KEY_SUFFIXES)
    )
    sensitive = "-----begin" in folded or any(
        term in compact for term in _SENSITIVE_IDENTIFIER_TERMS
    )
    if path_like or sensitive:
        raise ContractError(
            "sensitive_value",
            f"{field} must be a public identifier only",
        )
    return identity


def _require_m0_public_metadata(value: object, field: str) -> str:
    metadata = _require_text(value, field)
    folded = metadata.casefold()
    compact = _normalized_compact(metadata)
    if (
        "-----begin" in folded
        or any(term in compact for term in _SENSITIVE_IDENTIFIER_TERMS)
        or _CREDENTIAL_PREFIX_PATTERN.search(metadata) is not None
    ):
        raise ContractError(
            "sensitive_value",
            f"{field} must contain public metadata only",
        )
    looks_like_url = "://" in metadata
    if looks_like_url:
        try:
            parsed = urlsplit(metadata)
        except ValueError as error:
            raise ContractError(
                "sensitive_value",
                f"{field} must contain public metadata only",
            ) from error
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ContractError(
                "sensitive_value",
                f"{field} must contain public metadata only",
            )
        return metadata
    return _require_public_identifier(metadata, field)


def _require_m0_runtime_source(value: object, field: str) -> str:
    source = _require_text(value, field)
    if "?" in source or "#" in source:
        raise ContractError(
            "sensitive_value",
            f"{field} must be a public HTTPS URL",
        )
    source = _require_m0_public_metadata(source, field)
    try:
        parsed = urlsplit(source)
    except ValueError as error:
        raise ContractError(
            "sensitive_value",
            f"{field} must be a public HTTPS URL",
        ) from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ContractError(
            "sensitive_value",
            f"{field} must be a public HTTPS URL",
        )
    return source


@dataclass(frozen=True)
class SupplyArtifact:
    source: str
    version: str
    artifact_name: str
    url: str
    size: int
    sha256: str
    license_name: str
    license_url: str
    license_sha256: str
    supported_architecture: str

    @classmethod
    def from_mapping(
        cls,
        value: object,
        field: str,
    ) -> "SupplyArtifact":
        raw = _require_mapping(value, field)
        _require_exact_keys(raw, SUPPLY_ARTIFACT_KEYS, field)
        return cls(
            source=_require_text(raw["source"], f"{field}.source"),
            version=_require_text(raw["version"], f"{field}.version"),
            artifact_name=_require_text(raw["artifact_name"], f"{field}.artifact_name"),
            url=_require_https_url(raw["url"], f"{field}.url"),
            size=_require_positive_size(raw["size"], f"{field}.size"),
            sha256=_require_sha256(raw["sha256"], f"{field}.sha256"),
            license_name=_require_text(raw["license_name"], f"{field}.license_name"),
            license_url=_require_https_url(raw["license_url"], f"{field}.license_url"),
            license_sha256=_require_sha256(
                raw["license_sha256"],
                f"{field}.license_sha256",
            ),
            supported_architecture=_require_architecture(
                raw["supported_architecture"],
                f"{field}.supported_architecture",
            ),
        )


@dataclass(frozen=True)
class CertificateLock:
    provider: str
    subject: str
    issuer: str
    fingerprint: str
    key_identity: str
    valid_from: str
    valid_until: str
    storage_kind: str

    @classmethod
    def from_mapping(
        cls,
        value: object,
        now: datetime,
    ) -> "CertificateLock":
        field = "certificate"
        raw = _require_mapping(value, field)
        _require_exact_keys(raw, CERTIFICATE_KEYS, field)
        valid_from_text, valid_from = _require_rfc3339_utc(
            raw["valid_from"],
            f"{field}.valid_from",
        )
        valid_until_text, valid_until = _require_rfc3339_utc(
            raw["valid_until"],
            f"{field}.valid_until",
        )
        if valid_from >= valid_until:
            raise ContractError(
                "invalid_validity_window",
                "certificate validity window must be ordered",
            )
        if now < valid_from or now >= valid_until:
            raise ContractError(
                "certificate_not_current",
                "certificate is outside its validity window",
            )
        return cls(
            provider=_require_text(raw["provider"], f"{field}.provider"),
            subject=_require_text(raw["subject"], f"{field}.subject"),
            issuer=_require_text(raw["issuer"], f"{field}.issuer"),
            fingerprint=_require_sha256(raw["fingerprint"], f"{field}.fingerprint"),
            key_identity=_require_public_identifier(
                raw["key_identity"],
                f"{field}.key_identity",
            ),
            valid_from=valid_from_text,
            valid_until=valid_until_text,
            storage_kind=_require_public_identifier(
                raw["storage_kind"],
                f"{field}.storage_kind",
            ),
        )


@dataclass(frozen=True)
class TimestampLock:
    rfc3161_url: str
    digest: str

    @classmethod
    def from_mapping(cls, value: object) -> "TimestampLock":
        field = "timestamp"
        raw = _require_mapping(value, field)
        _require_exact_keys(raw, TIMESTAMP_KEYS, field)
        digest = _require_text(raw["digest"], f"{field}.digest")
        if digest != "sha256":
            raise ContractError(
                "unsupported_digest",
                f"{field}.digest must be sha256",
            )
        return cls(
            rfc3161_url=_require_https_url(
                raw["rfc3161_url"],
                f"{field}.rfc3161_url",
            ),
            digest=digest,
        )


@dataclass(frozen=True)
class WindowsSupplyLock:
    schema_version: int
    architecture: str
    certificate: CertificateLock
    timestamp: TimestampLock
    python_runtime: SupplyArtifact
    webview2: SupplyArtifact

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, object],
        now: datetime,
    ) -> "WindowsSupplyLock":
        _require_exact_keys(raw, REQUIRED_KEYS, "supply_lock")
        schema_version = raw["schema_version"]
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise ContractError("invalid_type", "schema_version must be an integer")
        if schema_version != 1:
            raise ContractError("unsupported_schema", "schema_version must be 1")
        return cls(
            schema_version=schema_version,
            architecture=_require_architecture(raw["architecture"], "architecture"),
            certificate=CertificateLock.from_mapping(raw["certificate"], now),
            timestamp=TimestampLock.from_mapping(raw["timestamp"]),
            python_runtime=SupplyArtifact.from_mapping(
                raw["python_runtime"],
                "python_runtime",
            ),
            webview2=SupplyArtifact.from_mapping(raw["webview2"], "webview2"),
        )


def validate_windows_supply_lock(
    raw: Mapping[str, object],
    *,
    now: datetime | None = None,
) -> WindowsSupplyLock:
    root = _require_mapping(raw, "supply_lock")
    return WindowsSupplyLock.from_mapping(root, _validation_time(now))


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate_key", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_windows_supply_lock(
    path: Path,
    *,
    now: datetime | None = None,
) -> WindowsSupplyLock:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("invalid_json", "invalid supply lock JSON") from error
    except (FileNotFoundError, IsADirectoryError, OSError) as error:
        raise ContractError("missing_lock", "cannot read supply lock") from error
    try:
        raw = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
    except ContractError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContractError("invalid_json", "invalid supply lock JSON") from error
    root = _require_mapping(raw, "supply_lock")
    return validate_windows_supply_lock(root, now=now)


def _require_local_evidence(path: Path, field: str) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError, OSError) as error:
        raise ContractError("missing_evidence", f"cannot read {field}") from error
    if not content.strip():
        raise ContractError("missing_evidence", f"{field} must not be empty")


def require_m0_contract(contract: object | None = None) -> object:
    if contract is None:
        try:
            module_name = (
                f"{__package__}.release_manifest"
                if __package__
                else "release_manifest"
            )
            contract = importlib.import_module(module_name)
        except Exception as error:
            raise ContractError(
                "m0_contract_unavailable",
                "M0 release manifest contract is unavailable",
            ) from error
    required_attributes = ("SCHEMA_VERSION", "PLATFORMS", "RUNTIME_FIELDS")
    if any(not hasattr(contract, attribute) for attribute in required_attributes):
        raise ContractError(
            "m0_contract_unavailable",
            "M0 release manifest contract is unavailable",
        )
    schema_version = getattr(contract, "SCHEMA_VERSION")
    platforms = getattr(contract, "PLATFORMS")
    runtime_fields = getattr(contract, "RUNTIME_FIELDS")
    try:
        contract_matches = (
            type(schema_version) is int
            and schema_version == 1
            and type(platforms) is tuple
            and platforms == ("macos", "windows")
            and runtime_fields
            == {"source", "version", "size", "sha256", "license"}
        )
    except TypeError:
        contract_matches = False
    if not contract_matches:
        raise ContractError(
            "m0_contract_mismatch",
            "M0 release manifest contract does not match",
        )
    return contract


def project_python_runtime(lock: WindowsSupplyLock) -> dict[str, object]:
    require_m0_contract()
    runtime = lock.python_runtime
    return {
        "source": _require_m0_runtime_source(runtime.url, "runtime.source"),
        "version": _require_m0_public_metadata(runtime.version, "runtime.version"),
        "size": _require_positive_size(runtime.size, "runtime.size"),
        "sha256": _require_sha256(runtime.sha256, "runtime.sha256").lower(),
        "license": _require_m0_public_metadata(
            runtime.license_name,
            "runtime.license",
        ),
    }


def _require_external_readback(lock: WindowsSupplyLock) -> None:
    require_m0_contract()
    project_python_runtime(lock)
    raise ContractError(
        "external_readback_required",
        "approved external readback is required",
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    now: datetime | None = None,
) -> int:
    parser = QuietArgumentParser(
        description="Validate an approved local Windows release supply lock.",
    )
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--upgrade-code-evidence", required=True, type=Path)
    args = parser.parse_args(argv)

    lock = load_windows_supply_lock(args.lock, now=now)
    _require_local_evidence(args.evidence, "supply evidence")
    _require_local_evidence(args.upgrade_code_evidence, "upgrade code evidence")
    _require_external_readback(lock)
    return 0


def run_cli(argv: Sequence[str] | None = None) -> int:
    try:
        return main(argv)
    except ContractError as error:
        print(error.code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run_cli())
