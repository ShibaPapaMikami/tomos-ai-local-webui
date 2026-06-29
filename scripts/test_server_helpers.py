import sys
from pathlib import Path
import base64
import tempfile
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


def test_asr_status_payload_shape() -> None:
    payload = server.asr_status_payload()
    assert payload["ok"] is True
    assert "available" in payload
    assert payload["status"] in {
        "ready",
        "not_configured",
        "needs_dependencies",
        "needs_compatible_nemo",
        "needs_model_download",
    }
    assert payload["recommendedModel"] == server.DEFAULT_ASR_MODEL
    assert payload["language"]
    assert "runnerConfigured" in payload
    assert isinstance(payload["requirements"], list)
    assert {item["id"] for item in payload["requirements"]} >= {
        "python",
        "ffmpeg",
        "torch",
        "cython",
        "packaging",
        "nemo",
        "nemotron_compat",
        "asr_model_cache",
    }
    assert isinstance(payload["requirementsOk"], bool)
    assert isinstance(payload["dependenciesOk"], bool)
    assert isinstance(payload["modelCache"], dict)
    assert isinstance(payload["runnableModels"], list)
    assert server.DEFAULT_ASR_MODEL in payload["runnableModels"]
    assert payload["setupDoc"].endswith("asr-nemotron-setup.ja.md")
    assert isinstance(payload["candidates"], list)
    assert {candidate["model"] for candidate in payload["candidates"]} >= {
        "nvidia/nemotron-3.5-asr-streaming-0.6b",
        "whisper.cpp:tiny",
        "whisper.cpp:large-v3-turbo",
        "vosk",
        "sherpa-onnx",
    }
    assert all(candidate.get("source") for candidate in payload["candidates"])
    assert any(candidate.get("implemented") for candidate in payload["candidates"])
    assert payload["nextStep"]


def test_asr_model_normalization() -> None:
    assert server.normalize_asr_model(server.DEFAULT_ASR_MODEL) == server.DEFAULT_ASR_MODEL
    expected_whisper = server.WHISPER_CPP_FAST_MODEL if server.whisper_cpp_available() else (server.ASR_MODEL or server.DEFAULT_ASR_MODEL)
    assert server.normalize_asr_model("whisper.cpp") == expected_whisper
    assert server.normalize_asr_model(server.WHISPER_CPP_FAST_MODEL) == expected_whisper


def test_whisper_cpp_status_shape() -> None:
    status = server.whisper_cpp_status()
    assert isinstance(status["available"], bool)
    assert "binary" in status
    assert "modelPath" in status
    assert "modelSizeText" in status


def test_asr_status_detects_nemotron_incompatible_nemo() -> None:
    previous_runner = server.ASR_RUNNER
    previous_status = server.asr_python_environment_status
    try:
        server.ASR_RUNNER = "python3 scripts/asr_nemotron_runner.py"
        server.asr_python_environment_status = lambda: {
            "version": "3.11.9",
            "executable": "python3",
            "modules": {
                "torch": True,
                "Cython": True,
                "packaging": True,
                "nemo.collections.asr": True,
                "nemo.collections.asr.models.rnnt_bpe_models_prompt": False,
            },
        }
        payload = server.asr_status_payload()
        assert payload["available"] is False
        assert payload["status"] == "needs_compatible_nemo"
        assert "NeMo main" in payload["message"]
        assert any(item["id"] == "nemotron_compat" and not item["ok"] for item in payload["requirements"])
    finally:
        server.ASR_RUNNER = previous_runner
        server.asr_python_environment_status = previous_status


def test_asr_runner_missing_is_clear() -> None:
    previous_runner = server.ASR_RUNNER
    try:
        server.ASR_RUNNER = ""
        try:
            server.run_asr_transcription(base64.b64encode(b"fake audio").decode("ascii"), "audio/webm", server.DEFAULT_ASR_MODEL)
        except RuntimeError as exc:
            assert "GEMMA_ASR_RUNNER" in str(exc)
        else:
            raise AssertionError("missing ASR runner should fail clearly")
    finally:
        server.ASR_RUNNER = previous_runner


def test_asr_suffix_for_mime() -> None:
    assert server.asr_suffix_for_mime("audio/wav") == ".wav"
    assert server.asr_suffix_for_mime("audio/mp4") == ".m4a"
    assert server.asr_suffix_for_mime("audio/ogg; codecs=opus") == ".ogg"
    assert server.asr_suffix_for_mime("audio/webm") == ".webm"


def test_asr_setup_status_shape() -> None:
    status = server.asr_setup_status()
    assert status["ok"] is True
    assert isinstance(status["job"], dict)


def test_workspace_document_type_search_expands_terms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "agreement.txt").write_text("業務委託の条件を記載します。\n", encoding="utf-8")
        (root / "memo.txt").write_text("ただのメモです。\n", encoding="utf-8")
        result = server.search_workspace_files(str(root), "契約書")
        assert result["terms"][0] == "契約書"
        assert "agreement" in [term.lower() for term in result["terms"]]
        assert result["results"]
        assert result["results"][0]["path"] == "agreement.txt"


def write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    paragraph_xml = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        for text in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraph_xml}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def test_workspace_search_reads_docx_text() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimal_docx(root / "notes.docx", ["初回打ち合わせ", "秘密保持契約の確認をします。"])
        result = server.search_workspace_files(str(root), "契約書")
        assert result["results"]
        assert result["results"][0]["path"] == "notes.docx"
        assert "秘密保持契約" in result["results"][0]["preview"]


def test_workspace_search_matches_binary_filename() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "契約書.pdf").write_bytes(b"%PDF-1.4\n%binary")
        result = server.search_workspace_files(str(root), "契約書")
        assert result["results"]
        assert result["results"][0]["path"] == "契約書.pdf"
        assert "ファイル名" in result["results"][0]["preview"]
        assert result["results"][0]["matchType"] == "filename"
        assert result["results"][0]["sourceKind"] == "pdf"
        assert "pdfUnreadable" in result


def test_pdf_text_falls_back_to_mdls() -> None:
    class FakeRunResult:
        returncode = 0
        stdout = "秘密保持契約のPDF本文です。"

    previous_which = server.shutil.which
    previous_run = server.subprocess.run
    try:
        server.shutil.which = lambda name: "/usr/bin/mdls" if name == "mdls" else ""
        server.subprocess.run = lambda *args, **kwargs: FakeRunResult()
        assert server.extract_pdf_text_with_mdls(Path("dummy.pdf")) == "秘密保持契約のPDF本文です。"
        capabilities = server.workspace_search_capabilities()
        assert capabilities["pdf"] is True
        assert capabilities["pdfBackend"] == "Spotlight"
    finally:
        server.shutil.which = previous_which
        server.subprocess.run = previous_run


def test_workspace_search_reads_pdf_text_with_mdls() -> None:
    class FakeRunResult:
        returncode = 0
        stdout = "秘密保持契約のPDF本文です。"

    previous_which = server.shutil.which
    previous_run = server.subprocess.run
    try:
        server.shutil.which = lambda name: "/usr/bin/mdls" if name == "mdls" else ""
        server.subprocess.run = lambda *args, **kwargs: FakeRunResult()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "document.pdf").write_bytes(b"%PDF-1.4\n%test")
            result = server.search_workspace_files(str(root), "秘密保持契約")
            assert result["results"]
            assert result["results"][0]["path"] == "document.pdf"
            assert "秘密保持契約" in result["results"][0]["preview"]
            assert result["results"][0]["matchType"] == "body"
            assert result["results"][0]["sourceKind"] == "pdf"
            assert result["pdfUnreadable"] == 0
    finally:
        server.shutil.which = previous_which
        server.subprocess.run = previous_run


def test_workspace_context_instructs_source_citation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "gundam.txt").write_text("ガンダムのメモです。\n", encoding="utf-8")
        context = server.build_workspace_context({
            "root": str(root),
            "files": [],
            "searchQuery": "gundam",
        })
        assert "本文一致の根拠は `path:line`" in context
        assert "ファイル名一致の根拠は `path`" in context
        assert "gundam.txt:1" in context
        assert "検索結果にない内容は推測せず" in context


def test_workspace_context_uses_codegraph_summary_when_ready() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous_cache_dir = server.CODEGRAPH_APP_CACHE_DIR
        try:
            server.CODEGRAPH_APP_CACHE_DIR = root / ".test-codegraph-cache"
            cache_path = server.codegraph_cache_path(root.resolve())
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                server.json.dumps({
                    "stats": {"files": 1, "skipped": 0},
                    "files": [{
                        "path": "app.js",
                        "language": "JavaScript",
                        "symbols": ["startApp"],
                        "imports": ["./ui.js"],
                    }],
                }),
                encoding="utf-8",
            )
            context = server.build_workspace_context({
                "root": str(root),
                "files": [],
                "codegraph": True,
            })
            assert "CODE UNDERSTANDING SUMMARY" in context
            assert "Treat file paths and symbols here as local workspace evidence" in context
            assert "app.js" in context
            assert "startApp" in context
        finally:
            server.CODEGRAPH_APP_CACHE_DIR = previous_cache_dir


def test_workspace_search_capabilities_shape() -> None:
    capabilities = server.workspace_search_capabilities()
    assert capabilities["text"] is True
    assert capabilities["docx"] is True
    assert "pdf" in capabilities
    assert "pdfBackend" in capabilities
    assert capabilities["filenameFallback"] is True
    assert isinstance(capabilities["imageOcr"], bool)


def test_external_llm_url_allows_only_localhost() -> None:
    assert server.normalize_local_llm_base_url("") == server.OLLAMA_URL
    assert server.normalize_local_llm_base_url("http://127.0.0.1:8080/") == "http://127.0.0.1:8080"
    assert server.normalize_local_llm_base_url("http://localhost:8080") == "http://localhost:8080"
    try:
        server.normalize_local_llm_base_url("https://example.com")
    except ValueError as exc:
        assert "localhost" in str(exc) or "127.0.0.1" in str(exc)
    else:
        raise AssertionError("non-local LLM URL should be rejected")


def test_mobile_connect_info_localhost_uses_lan_candidates_for_qr() -> None:
    payload = server.mobile_connect_info(
        "127.0.0.1",
        54876,
        lan_addresses=["192.168.1.20"],
        public_port=54877,
    )
    assert payload["ok"] is True
    assert payload["lanAccessEnabled"] is True
    assert payload["pairingEnabled"] is True
    assert payload["bindHost"] == "127.0.0.1"
    assert payload["port"] == 54876
    assert payload["pairingCode"].isdigit()
    assert len(payload["pairingCode"]) == 6
    assert payload["hostCandidates"] == ["http://192.168.1.20:54877"]
    assert payload["qrPayload"]["host"] == "http://192.168.1.20:54877"
    assert payload["qrPayload"]["pairingCode"] == payload["pairingCode"]
    assert datetime.fromisoformat(payload["expiresAt"].replace("Z", "+00:00")) > datetime.now(timezone.utc)


def test_mobile_connect_info_lan_host_builds_pairing_payload() -> None:
    payload = server.mobile_connect_info("0.0.0.0", 54876, lan_addresses=["192.168.1.20"])
    assert payload["ok"] is True
    assert payload["lanAccessEnabled"] is True
    assert payload["pairingEnabled"] is True
    assert payload["hostCandidates"] == ["http://192.168.1.20:54876"]
    assert payload["qrPayload"]["host"] == "http://192.168.1.20:54876"
    assert payload["qrPayload"]["pairingCode"] == payload["pairingCode"]
    assert payload["qrPayload"]["expiresAt"] == payload["expiresAt"]


def test_mobile_connect_info_reuses_active_pairing_code() -> None:
    previous_state = server.MOBILE_PAIRING_STATE.copy()
    try:
        server.MOBILE_PAIRING_STATE.clear()
        first = server.mobile_connect_info("0.0.0.0", 54876, lan_addresses=["192.168.1.20"], now=1000)
        second = server.mobile_connect_info("0.0.0.0", 54876, lan_addresses=["192.168.1.20"], now=1005)
        assert second["pairingCode"] == first["pairingCode"]
        assert second["expiresAt"] == first["expiresAt"]

        expired = server.mobile_connect_info(
            "0.0.0.0",
            54876,
            lan_addresses=["192.168.1.20"],
            now=1000 + server.MOBILE_PAIRING_TTL_SECONDS + 1,
        )
        assert expired["pairingCode"] != first["pairingCode"]
        assert expired["expiresAt"] != first["expiresAt"]
    finally:
        server.MOBILE_PAIRING_STATE.clear()
        server.MOBILE_PAIRING_STATE.update(previous_state)


def test_mobile_chat_import_requires_current_pairing_code() -> None:
    previous_state = server.MOBILE_PAIRING_STATE.copy()
    previous_imports = list(server.MOBILE_PENDING_IMPORTS)
    try:
        server.MOBILE_PENDING_IMPORTS.clear()
        info = server.mobile_connect_info("0.0.0.0", 54876, lan_addresses=["192.168.1.20"], now=1000)
        payload = {
            "type": "gemma4-mobile-chat",
            "messages": [
                {"role": "user", "text": "こんにちは"},
                {"role": "assistant", "text": "こんにちは。"},
            ],
        }
        rejected = server.queue_mobile_chat_import({"pairingCode": "000000", "payload": payload}, now=1001)
        assert rejected["ok"] is False
        assert rejected["error"] == "invalid_pairing_code"

        accepted = server.queue_mobile_chat_import({"pairingCode": info["pairingCode"], "payload": payload}, now=1001)
        assert accepted["ok"] is True
        assert accepted["summary"]["total"] == 2
        assert len(server.mobile_pending_imports()) == 1
        assert server.mobile_pending_imports()[0]["payload"]["messages"][0]["text"] == "こんにちは"
    finally:
        server.MOBILE_PAIRING_STATE.clear()
        server.MOBILE_PAIRING_STATE.update(previous_state)
        server.MOBILE_PENDING_IMPORTS.clear()
        server.MOBILE_PENDING_IMPORTS.extend(previous_imports)


def test_mobile_chat_import_ignores_duplicate_payload() -> None:
    previous_state = server.MOBILE_PAIRING_STATE.copy()
    previous_imports = list(server.MOBILE_PENDING_IMPORTS)
    try:
        server.MOBILE_PENDING_IMPORTS.clear()
        info = server.mobile_connect_info("0.0.0.0", 54876, lan_addresses=["192.168.1.20"], now=1000)
        payload = {
            "type": "gemma4-mobile-chat",
            "exportedAt": "2026-06-27T10:00:00Z",
            "messages": [
                {"id": "m1", "role": "user", "text": "同じ内容", "createdAt": "2026-06-27T10:00:00Z"},
                {"id": "m2", "role": "assistant", "text": "同じ返答", "createdAt": "2026-06-27T10:00:01Z"},
            ],
        }

        first = server.queue_mobile_chat_import({"pairingCode": info["pairingCode"], "payload": payload}, now=1001)
        second = server.queue_mobile_chat_import({"pairingCode": info["pairingCode"], "payload": payload}, now=1002)

        assert first["ok"] is True
        assert second["ok"] is True
        assert second["duplicate"] is True
        assert second["importId"] == first["importId"]
        assert len(server.mobile_pending_imports()) == 1
    finally:
        server.MOBILE_PAIRING_STATE.clear()
        server.MOBILE_PAIRING_STATE.update(previous_state)
        server.MOBILE_PENDING_IMPORTS.clear()
        server.MOBILE_PENDING_IMPORTS.extend(previous_imports)


def test_mobile_preview_urls_use_lan_addresses() -> None:
    urls = server.mobile_preview_urls(54876, lan_addresses=["192.168.1.20", "10.0.0.5"])
    assert urls == ["http://10.0.0.5:54876", "http://192.168.1.20:54876"]


def test_mobile_static_routes_include_pc_mobile_connect_alias() -> None:
    assert server.static_preview_get_api_allowed("/pc-mobile-connect") is True


def test_static_preview_blocks_non_health_get_api() -> None:
    assert server.static_preview_get_api_allowed("/api/health") is True
    assert server.static_preview_get_api_allowed("/api/mobile/connect-info") is False
    assert server.static_preview_get_api_allowed("/api/workspace/preview") is False
    assert server.static_preview_get_api_allowed("/api/image/view") is False
    assert server.static_preview_get_api_allowed("/manifest.webmanifest") is True


def test_mobile_sync_allows_only_mobile_api() -> None:
    assert server.static_preview_get_api_allowed("/api/health", allow_mobile_sync=True) is True
    assert server.static_preview_get_api_allowed("/api/mobile/connect-info", allow_mobile_sync=True) is True
    assert server.static_preview_get_api_allowed("/api/mobile/imports", allow_mobile_sync=True) is True
    assert server.static_preview_get_api_allowed("/api/chat", allow_mobile_sync=True) is False
    assert server.static_preview_get_api_allowed("/api/workspace/preview", allow_mobile_sync=True) is False
    assert server.static_preview_get_api_allowed("/mobile.html", allow_mobile_sync=True) is True


def test_mobile_api_access_limits_pairing_and_imports_to_local_pc() -> None:
    assert server.mobile_api_access_allowed("POST", "/api/mobile/import-chat", "192.168.1.40") is True
    assert server.mobile_api_access_allowed("GET", "/api/mobile/connect-info", "127.0.0.1") is True
    assert server.mobile_api_access_allowed("GET", "/api/mobile/qr.svg", "127.0.0.1") is True
    assert server.mobile_api_access_allowed("GET", "/api/mobile/imports", "127.0.0.1") is True
    assert server.mobile_api_access_allowed("POST", "/api/mobile/imports/clear", "127.0.0.1") is True
    assert server.mobile_api_access_allowed("GET", "/api/mobile/connect-info", "192.168.1.40") is False
    assert server.mobile_api_access_allowed("GET", "/api/mobile/qr.svg", "192.168.1.40") is False
    assert server.mobile_api_access_allowed("GET", "/api/mobile/imports", "192.168.1.40") is False
    assert server.mobile_api_access_allowed("POST", "/api/mobile/imports/clear", "192.168.1.40") is False


def test_mobile_api_access_allows_pc_lan_address_for_management_apis() -> None:
    original = server.local_lan_ipv4_addresses
    try:
        server.local_lan_ipv4_addresses = lambda: ["192.168.1.20"]
        assert server.mobile_api_access_allowed("GET", "/api/mobile/connect-info", "192.168.1.20") is True
        assert server.mobile_api_access_allowed("GET", "/api/mobile/qr.svg", "192.168.1.20") is True
        assert server.mobile_api_access_allowed("GET", "/api/mobile/imports", "192.168.1.40") is False
    finally:
        server.local_lan_ipv4_addresses = original


def test_mobile_qr_svg_contains_svg_modules() -> None:
    svg = server.mobile_qr_svg("http://192.168.1.20:54877/m")
    assert svg.startswith("<svg")
    assert 'class="segno"' in svg
    assert "<path" in svg
    assert "#000" in svg


def test_decode_subprocess_output_handles_invalid_locale_bytes() -> None:
    text = server.decode_subprocess_output(b"\x81\x00pulling manifest\n")
    assert "pulling manifest" in text


def test_iter_subprocess_output_lines_handles_binary_lines() -> None:
    class FakeProcess:
        stdout = [b"\x81\x00pulling manifest\n", "success\n"]

    lines = list(server.iter_subprocess_output_lines(FakeProcess()))
    assert "pulling manifest" in lines[0]
    assert lines[1] == "success"


if __name__ == "__main__":
    test_asr_status_payload_shape()
    test_asr_model_normalization()
    test_whisper_cpp_status_shape()
    test_asr_status_detects_nemotron_incompatible_nemo()
    test_asr_runner_missing_is_clear()
    test_asr_suffix_for_mime()
    test_asr_setup_status_shape()
    test_workspace_document_type_search_expands_terms()
    test_workspace_search_reads_docx_text()
    test_workspace_search_matches_binary_filename()
    test_pdf_text_falls_back_to_mdls()
    test_workspace_search_reads_pdf_text_with_mdls()
    test_workspace_context_instructs_source_citation()
    test_workspace_context_uses_codegraph_summary_when_ready()
    test_workspace_search_capabilities_shape()
    test_external_llm_url_allows_only_localhost()
    test_mobile_connect_info_localhost_uses_lan_candidates_for_qr()
    test_mobile_connect_info_lan_host_builds_pairing_payload()
    test_mobile_connect_info_reuses_active_pairing_code()
    test_mobile_chat_import_requires_current_pairing_code()
    test_mobile_chat_import_ignores_duplicate_payload()
    test_mobile_preview_urls_use_lan_addresses()
    test_mobile_static_routes_include_pc_mobile_connect_alias()
    test_static_preview_blocks_non_health_get_api()
    test_mobile_sync_allows_only_mobile_api()
    test_mobile_api_access_limits_pairing_and_imports_to_local_pc()
    test_mobile_api_access_allows_pc_lan_address_for_management_apis()
    test_mobile_qr_svg_contains_svg_modules()
    test_decode_subprocess_output_handles_invalid_locale_bytes()
    test_iter_subprocess_output_lines_handles_binary_lines()
    print("server helper tests passed")
