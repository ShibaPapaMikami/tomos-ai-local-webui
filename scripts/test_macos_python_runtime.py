from __future__ import annotations

import hashlib
import io
import importlib.util
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request

from macos_python_runtime import (
    ARTIFACT,
    RuntimeArtifact,
    extract_runtime,
    publish_runtime,
    stage_runtime,
    verify_artifact,
    verify_artifact_file,
)


def make_runtime_tar(tmp_path: Path, member_name: str) -> Path:
    archive = tmp_path / "runtime.tar.gz"
    payload = b"fixture"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo(member_name)
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))
    return archive


def make_valid_runtime_tar(
    tmp_path: Path,
    *,
    link_name: str | None = "python/bin/python3",
    link_target: str | None = "python3.11",
    hardlink: bool = False,
    include_license: bool = True,
) -> Path:
    archive = tmp_path / "valid-runtime.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for directory in ("python", "python/bin", "python/lib/python3.11"):
            member = tarfile.TarInfo(directory)
            member.type = tarfile.DIRTYPE
            tar.addfile(member)

        executable = tarfile.TarInfo("python/bin/python3.11")
        executable.mode = 0o755
        executable.size = 1
        tar.addfile(executable, io.BytesIO(b"x"))

        if include_license:
            license_file = tarfile.TarInfo("python/lib/python3.11/LICENSE.txt")
            license_file.size = 7
            tar.addfile(license_file, io.BytesIO(b"license"))

        if link_name is not None and link_target is not None:
            link = tarfile.TarInfo(link_name)
            link.type = tarfile.LNKTYPE if hardlink else tarfile.SYMTYPE
            link.linkname = link_target
            tar.addfile(link)
    return archive


def test_rejects_wrong_hash(tmp_path: Path) -> None:
    archive = tmp_path / ARTIFACT.name
    archive.write_bytes(b"wrong")
    artifact = RuntimeArtifact(
        name=ARTIFACT.name,
        url=ARTIFACT.url,
        sha256=ARTIFACT.sha256,
        size=archive.stat().st_size,
    )
    try:
        verify_artifact(archive, artifact)
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("wrong hash was accepted")


def test_rejects_wrong_size(tmp_path: Path) -> None:
    archive = tmp_path / "size.tar.gz"
    archive.write_bytes(b"size")
    artifact = RuntimeArtifact(
        name=archive.name,
        url=ARTIFACT.url,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        size=archive.stat().st_size + 1,
    )
    try:
        verify_artifact(archive, artifact)
    except ValueError as exc:
        assert "サイズ" in str(exc)
    else:
        raise AssertionError("wrong size was accepted")


def test_rejects_unsafe_tar_member(tmp_path: Path) -> None:
    archive = make_runtime_tar(tmp_path, member_name="../outside")
    try:
        extract_runtime(archive, tmp_path / "runtime-unsafe")
    except ValueError as exc:
        assert "安全" in str(exc)
    else:
        raise AssertionError("unsafe tar member was accepted")


def test_allows_allowlisted_symlink_and_official_license_path(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(
        tmp_path, link_name="python/bin/python3", link_target="python3.11"
    )
    runtime = extract_runtime(archive, tmp_path / "runtime")
    assert (runtime / "bin/python3").is_symlink()
    assert (runtime / "lib/python3.11/LICENSE.txt").is_file()


def test_rejects_unregistered_symlink(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(
        tmp_path, link_name="python/bin/unregistered", link_target="python3.11"
    )
    try:
        extract_runtime(archive, tmp_path / "runtime-unregistered")
    except ValueError as exc:
        assert "安全" in str(exc)
    else:
        raise AssertionError("unregistered symlink was accepted")


def test_rejects_symlink_with_external_target(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(
        tmp_path, link_name="python/bin/python3", link_target="/outside"
    )
    try:
        extract_runtime(archive, tmp_path / "runtime-external")
    except ValueError as exc:
        assert "安全" in str(exc)
    else:
        raise AssertionError("external symlink target was accepted")


def test_rejects_symlink_with_parent_target(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(
        tmp_path, link_name="python/bin/python3", link_target="../python3.11"
    )
    try:
        extract_runtime(archive, tmp_path / "runtime-parent-target")
    except ValueError as exc:
        assert "安全" in str(exc)
    else:
        raise AssertionError("parent symlink target was accepted")


def test_rejects_hardlink(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(
        tmp_path,
        link_name="python/bin/python3",
        link_target="python/bin/python3.11",
        hardlink=True,
    )
    try:
        extract_runtime(archive, tmp_path / "runtime-hardlink")
    except ValueError as exc:
        assert "安全" in str(exc)
    else:
        raise AssertionError("hardlink was accepted")


def test_allows_only_explicit_release_asset_host() -> None:
    module = _load_fetch_module()

    module._require_allowed_host("https://release-assets.githubusercontent.com/runtime")
    try:
        module._require_allowed_host("https://sub.release-assets.githubusercontent.com/runtime")
    except ValueError:
        pass
    else:
        raise AssertionError("release asset subdomain was accepted")


def test_redirect_handler_rejects_http_and_unknown_hosts() -> None:
    module = _load_fetch_module()
    handler = module.AllowedRedirectHandler()
    request = Request("https://github.com/example")
    for url in ("http://github.com/runtime", "https://example.com/runtime"):
        try:
            handler.redirect_request(request, None, 302, "Found", {}, url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe redirect was accepted: {url}")


def test_verified_file_descriptor_survives_path_replacement(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(tmp_path)
    artifact = RuntimeArtifact(
        name=archive.name,
        url=ARTIFACT.url,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        size=archive.stat().st_size,
    )
    with archive.open("rb") as source:
        verify_artifact_file(source, artifact)
        replacement = tmp_path / "replacement.tar.gz"
        replacement.write_bytes(b"replaced")
        os.replace(replacement, archive)
        staging = stage_runtime(source, tmp_path / "runtime")
    try:
        assert (staging / "lib/python3.11/LICENSE.txt").is_file()
    finally:
        shutil.rmtree(staging)


def test_staging_failure_cleans_up_and_does_not_publish(tmp_path: Path) -> None:
    archive = make_valid_runtime_tar(tmp_path, include_license=False)
    destination = tmp_path / "runtime-staging-failure"
    try:
        with archive.open("rb") as source:
            stage_runtime(source, destination)
    except ValueError as exc:
        assert "LICENSE" in str(exc)
    else:
        raise AssertionError("runtime without license was staged")
    assert not destination.exists()
    assert not list(tmp_path.glob(".runtime.*"))


def test_cpu_failure_does_not_publish_destination(tmp_path: Path) -> None:
    module = _load_fetch_module()
    archive = make_valid_runtime_tar(tmp_path)
    destination = tmp_path / "runtime-cpu-failure"

    def reject_cpu(_python: Path) -> str:
        raise ValueError("not arm64")

    try:
        with archive.open("rb") as source:
            module.install_verified_runtime(source, destination, reject_cpu)
    except ValueError as exc:
        assert "arm64" in str(exc)
    else:
        raise AssertionError("runtime with invalid CPU was published")
    assert not destination.exists()
    assert not list(tmp_path.glob(".runtime.*"))


def _load_fetch_module():
    module_path = Path(__file__).with_name("fetch-macos-python-runtime.py")
    spec = importlib.util.spec_from_file_location("fetch_macos_python_runtime", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        tmp_path = Path(directory)
        test_rejects_wrong_hash(tmp_path)
        test_rejects_wrong_size(tmp_path)
        test_rejects_unsafe_tar_member(tmp_path)
        test_allows_allowlisted_symlink_and_official_license_path(tmp_path)
        test_rejects_unregistered_symlink(tmp_path)
        test_rejects_symlink_with_external_target(tmp_path)
        test_rejects_symlink_with_parent_target(tmp_path)
        test_rejects_hardlink(tmp_path)
        test_allows_only_explicit_release_asset_host()
        test_redirect_handler_rejects_http_and_unknown_hosts()
        test_verified_file_descriptor_survives_path_replacement(tmp_path)
        test_staging_failure_cleans_up_and_does_not_publish(tmp_path)
        test_cpu_failure_does_not_publish_destination(tmp_path)
    print("macOS Python runtime tests passed")


if __name__ == "__main__":
    main()
