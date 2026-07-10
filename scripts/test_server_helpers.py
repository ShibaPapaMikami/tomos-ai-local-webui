import sys
from pathlib import Path
import base64
import tempfile
import zipfile
import urllib.error
from datetime import datetime, timezone
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server
import sarashina_ocr_runner


def test_person_photo_upload_saves_to_local_folder() -> None:
    previous_dir = server.PERSON_PHOTO_DIR
    with tempfile.TemporaryDirectory() as tmp:
        try:
            server.PERSON_PHOTO_DIR = Path(tmp)
            payload = server.person_photo_upload_payload(
                "avatar.png",
                "image/png",
                base64.b64encode(b"\x89PNG\r\n\x1a\nsample").decode("ascii"),
            )
            assert (Path(tmp) / payload["file"]).is_file()
        finally:
            server.PERSON_PHOTO_DIR = previous_dir
    assert payload["ok"] is True
    assert payload["file"].endswith(".png")
    assert payload["url"].startswith("/api/person-photo/view?file=")
    assert payload["size"] > 0


def test_person_photo_upload_rejects_unsupported_mime() -> None:
    payload = server.person_photo_upload_payload(
        "avatar.gif",
        "image/gif",
        base64.b64encode(b"gif").decode("ascii"),
    )
    assert payload["ok"] is False
    assert "unsupported" in payload["error"]


def test_contract_pdf_import_status_payload_shape() -> None:
    payload = server.contract_pdf_import_status_payload()
    assert payload["ok"] is True
    pdf_import = payload["pdfImport"]
    assert pdf_import["id"] == "contract-pdf-import"
    assert pdf_import["status"] == "not-connected"
    assert pdf_import["runnerConnected"] is False
    assert pdf_import["defaultEnabled"] is True
    model_ids = {model["id"] for model in pdf_import["models"]}
    assert {"glm-ocr", "sarashina2.2-ocr"}.issubset(model_ids)


def test_contract_pdf_import_connection_test_payload_shape() -> None:
    payload = server.contract_pdf_import_connection_test_payload()
    assert payload["ok"] is True
    assert payload["pdfImportId"] == "contract-pdf-import"
    assert payload["runnerConnected"] is False
    assert payload["testMode"] == "local-baseline"
    baseline = payload["baselineOcr"]
    assert "available" in baseline
    assert "engine" in baseline
    assert "pdf" in baseline
    assert "image" in baseline


def test_sarashina_ocr_status_payload_shape() -> None:
    payload = sarashina_ocr_runner.sarashina_ocr_status()
    assert payload["ok"] is True
    assert payload["id"] == "sarashina2.2-ocr"
    assert payload["model"] == "sbintuitions/sarashina2.2-ocr"
    assert payload["status"] in {"ready", "needs_dependencies", "needs_model_download"}
    assert isinstance(payload["missing"], list)
    assert payload["externalApi"] is False


def test_sarashina_compare_page_rejects_missing_path() -> None:
    payload = sarashina_ocr_runner.sarashina_compare_page_payload("")
    assert payload["ok"] is False
    assert "PDF" in payload["error"]
    assert payload["sarashina"]["id"] == "sarashina2.2-ocr"


def test_contract_pdf_import_try_page_rejects_missing_path() -> None:
    payload = server.contract_pdf_import_try_page_payload("")
    assert payload["ok"] is False
    assert "PDF" in payload["error"]


def test_contract_pdf_import_try_page_payload_preview(monkeypatch=None) -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        path = Path(tmp.name)
        previous = server.extract_pdf_page_text
        try:
            server.extract_pdf_page_text = lambda source, page=1: "秘密保持契約書\u200b\n                                  \u200b\n株式会社BeBlock\u200b\n   契約期間は3年間です。"
            payload = server.contract_pdf_import_try_page_payload(str(path), page=2)
        finally:
            server.extract_pdf_page_text = previous
    assert payload["ok"] is True
    assert payload["pdfImportId"] == "contract-pdf-import"
    assert payload["runner"] == "local-baseline"
    assert payload["sourcePath"].endswith(".pdf")
    assert payload["page"] == 2
    assert payload["textLength"] > 0
    assert "秘密保持契約書" in payload["preview"]
    assert "\u200b" not in payload["preview"]
    assert "                                  " not in payload["preview"]
    assert "株式会社BeBlock" in payload["preview"]
    assert payload["contractCandidate"]["contractName"] == "秘密保持契約書"
    assert payload["contractCandidate"]["counterpartyName"] == "株式会社BeBlock"
    assert payload["contractCandidate"]["sourceType"] == "contract-pdf-import"
    assert payload["contractCandidate"]["extractionJson"]["sourceType"] == "contract-pdf-import"


def test_contract_pdf_import_try_all_pages_payload_preview(monkeypatch=None) -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        path = Path(tmp.name)
        previous = server.extract_pdf_text
        previous_page = server.extract_pdf_page_text
        previous_count = server.pdf_page_count
        try:
            server.extract_pdf_text = lambda source: (
                "秘密保持契約書\n株式会社BeBlock（以下「委託者」）と、株式会社Gugenka（以下「受託者」）\n"
                "委託者受託者間の2026年6月25日付の業務委託契約書に基づき秘密保持契約を締結した。\n"
                "本契約は、2027年6月25日付の業務委託契約書の契約終了日までとし、"
                "第1条、第2条、第5条、第6条及び第7条の規定は、業務委託契約終了日から3年間に限り効力を有するものとする。"
            )
            server.extract_pdf_page_text = lambda source, page=1: f"ページ{page}の秘密保持契約プレビュー"
            server.pdf_page_count = lambda source: 2
            payload = server.contract_pdf_import_try_page_payload(str(path), page=1, all_pages=True)
        finally:
            server.extract_pdf_text = previous
            server.extract_pdf_page_text = previous_page
            server.pdf_page_count = previous_count
    assert payload["ok"] is True
    assert payload["allPages"] is True
    assert payload["page"] == "all"
    assert payload["contractCandidate"]["contractName"] == "秘密保持契約書"
    assert payload["contractCandidate"]["counterpartyName"] == "株式会社BeBlock"
    assert payload["contractCandidate"]["startDate"] == "2026-06-25"
    assert payload["contractCandidate"]["endDate"] == ""
    assert payload["contractCandidate"]["notes"].startswith("業務委託契約終了日から3年間")
    assert len(payload["pagePreviews"]) == 2
    assert payload["pagePreviews"][0]["page"] == 1
    assert "ページ1" in payload["pagePreviews"][0]["preview"]


def test_contract_pdf_import_auto_payload_prefers_pdf_text(monkeypatch=None) -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        path = Path(tmp.name)
        previous_pdftotext = server.extract_pdf_text_with_pdftotext
        previous_mdls = server.extract_pdf_text_with_mdls
        previous_count = server.pdf_page_count
        try:
            server.extract_pdf_text_with_pdftotext = lambda source: (
                "秘密保持契約書\n株式会社BeBlock（以下「委託者」）と、株式会社Gugenka（以下「受託者」）\n"
                "委託者受託者間の2026年6月25日付の業務委託契約書に基づき秘密保持契約を締結した。\n"
                "本契約において秘密情報とは、開示される全ての情報のうち秘密に保持すべきものをいう。"
                "受領当事者は秘密情報を厳格に管理し、第三者に開示又は漏洩してはならない。"
                "委託業務終了後も、秘密情報に関する書面、電子データ等を返却または廃棄し、"
                "本契約により知り得た秘密情報を委託業務終了前と同様に管理しなければならない。"
            )
            server.extract_pdf_text_with_mdls = lambda source: ""
            server.pdf_page_count = lambda source: 1
            payload = server.contract_pdf_import_auto_payload(str(path))
        finally:
            server.extract_pdf_text_with_pdftotext = previous_pdftotext
            server.extract_pdf_text_with_mdls = previous_mdls
            server.pdf_page_count = previous_count
    assert payload["ok"] is True
    assert payload["method"] == "pdf-text"
    assert payload["runnerLabel"] == "PDFテキスト抽出"
    assert "OCRは使っていません" in payload["reason"]
    assert payload["contractCandidate"]["contractName"] == "秘密保持契約書"


def test_contract_import_gap_payload_lists_unimported_pdf_and_docx() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        imported_pdf = root / "imported.pdf"
        missing_pdf = root / "missing.pdf"
        missing_docx = root / "missing.docx"
        ignored_txt = root / "memo.txt"
        imported_pdf.write_bytes(b"%PDF-1.4\n%imported")
        missing_pdf.write_bytes(b"%PDF-1.4\n%missing")
        write_minimal_docx(missing_docx, ["秘密保持契約書", "株式会社サンプル"])
        ignored_txt.write_text("秘密保持契約", encoding="utf-8")

        payload = server.contract_import_gap_payload(
            root_path=root,
            folder_id="folder-a",
            contracts=[
                {"sourcePath": str(imported_pdf)},
            ],
        )

    assert payload["ok"] is True
    assert payload["checked"] == 3
    assert payload["imported"] == 1
    assert payload["missing"] == 2
    assert [item["relativePath"] for item in payload["items"]] == [
        "missing.docx",
        "missing.pdf",
    ]
    assert {item["kind"] for item in payload["items"]} == {"Word", "PDF"}


def test_normalize_pdf_import_preview_text_removes_pdf_noise() -> None:
    text = server.normalize_pdf_import_preview_text(
        "秘密保持契約書\u200b\n                                  \u200b\n"
        "株式会社BeBlock\u200b（以下「委託者」）と、\u200b株式会社Gugenka\u200b（以下「受託者」）\n"
        "                       \u200b「受領当事者」という）"
    )
    assert "\u200b" not in text
    assert "                                  " not in text
    assert "株式会社BeBlock（以下「委託者」）と、株式会社Gugenka（以下「受託者」）" in text
    assert "「受領当事者」という）" in text


def test_normalize_pdf_import_preview_text_repairs_split_dates() -> None:
    text = server.normalize_pdf_import_preview_text("委託者受託者間の2026年\n\n6 25 月 日付の業務委託契約書")
    assert "2026年6月25日付" in text


def test_contract_pdf_payload_from_path_accepts_pdf() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        payload = server.contract_pdf_payload_from_path(tmp.name)
    assert payload["ok"] is True
    assert payload["path"].endswith(".pdf")


def test_clamp_pdf_page_number() -> None:
    assert server.clamp_pdf_page_number("2") == 2
    assert server.clamp_pdf_page_number("-1") == 1
    assert server.clamp_pdf_page_number("abc") == 1
    assert server.clamp_pdf_page_number("999") == 100


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


def test_workspace_contract_search_ignores_loose_outsourcing_hits() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "【20260629】秘密保持契約書 BeBlock.pdf").write_bytes(b"%PDF-1.4\n%binary")
        (root / "mail.txt").write_text("昨日業務委託から添付のような報告をもらいました。\n", encoding="utf-8")
        (root / "gundam.txt").write_text("【キャラクター：孫悟空（Son Goku）】\n■基本属性・性格\n", encoding="utf-8")

        result = server.search_workspace_files(str(root), "契約書")

        assert "業務委託" not in result["terms"]
        assert [item["path"] for item in result["results"]] == ["【20260629】秘密保持契約書 BeBlock.pdf"]
        assert result["results"][0]["matchType"] == "filename"


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
            "searchQuery": "ガンダム",
        })
        assert "本文一致の根拠は `path:line`" in context
        assert "ファイル名一致の根拠は `path`" in context
        assert "gundam.txt:1" in context
        assert "検索結果にない内容は推測せず" in context


def test_workspace_context_uses_context_record_adapter_for_knowledge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = Path(tmp) / "knowledge.sqlite"
        previous_db_path = server.KNOWLEDGE_DB_PATH
        try:
            server.KNOWLEDGE_DB_PATH = db_path
            (root / "memo.md").write_text("教材パックの確認は本日中に行います。\n", encoding="utf-8")
            server.index_knowledge_folder(
                db_path=db_path,
                folder_id="folder-1",
                root_path=root,
                extract_text=server.extract_knowledge_text,
            )
            context = server.build_workspace_context({
                "root": str(root),
                "files": [],
                "folderId": "folder-1",
                "knowledge": True,
                "searchQuery": "教材パック",
            })
        finally:
            server.KNOWLEDGE_DB_PATH = previous_db_path

    assert "ローカル資料から取得した文脈" in context
    assert "memo.md" in context
    assert "教材パック" in context
    assert "SQLite索引" in context


def test_context_memory_payloads_save_list_and_forget() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "context.sqlite"
        previous_context_db = server.CONTEXT_DB_PATH
        try:
            server.CONTEXT_DB_PATH = db_path
            saved = server.context_memory_save_payload({
                "item": {
                    "text": "ユーザーは短い箇条書きを好む",
                    "memoryType": "preference",
                    "sourceType": "manual",
                    "sourceId": "manual-1",
                },
                "scope": {
                    "scopeType": "folder",
                    "scopeId": "folder-1",
                    "ownerType": "user",
                    "ownerId": "local-user",
                },
            })
            assert saved["ok"] is True
            assert saved["record"]["metadata"]["memoryType"] == "preference"

            listed = server.context_memory_list_payload({"scopeType": "folder", "scopeId": "folder-1"})
            assert listed["ok"] is True
            assert len(listed["records"]) == 1
            assert listed["records"][0]["snippet"] == "ユーザーは短い箇条書きを好む"

            forgotten = server.context_memory_forget_payload({"id": saved["record"]["id"], "reason": "不要"})
            assert forgotten["ok"] is True
            assert forgotten["record"]["status"] == "deleted"

            after = server.context_memory_list_payload({"scopeType": "folder", "scopeId": "folder-1"})
            assert after["records"] == []
        finally:
            server.CONTEXT_DB_PATH = previous_context_db


def test_context_memory_profile_payload_separates_stable_and_recent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "context.sqlite"
        previous_context_db = server.CONTEXT_DB_PATH
        try:
            server.CONTEXT_DB_PATH = db_path
            server.context_memory_save_payload({
                "item": {
                    "text": "ユーザーは短い箇条書きを好む",
                    "memoryType": "preference",
                    "sourceType": "manual",
                    "sourceId": "manual-1",
                },
                "scope": {"scopeType": "folder", "scopeId": "folder-1"},
            })
            server.context_memory_save_payload({
                "item": {
                    "text": "今日は長期記憶機能の実装を進めた",
                    "memoryType": "activity",
                    "sourceType": "chat",
                    "sourceId": "message-1",
                },
                "scope": {"scopeType": "folder", "scopeId": "folder-1"},
            })
            payload = server.context_memory_profile_payload({"scopeType": "folder", "scopeId": "folder-1"})
        finally:
            server.CONTEXT_DB_PATH = previous_context_db

    assert payload["ok"] is True
    assert payload["stableFacts"][0]["snippet"] == "ユーザーは短い箇条書きを好む"
    assert payload["recentActivities"][0]["snippet"] == "今日は長期記憶機能の実装を進めた"


def test_context_memory_update_payload_updates_saved_memory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "context.sqlite"
        previous_context_db = server.CONTEXT_DB_PATH
        try:
            server.CONTEXT_DB_PATH = db_path
            saved = server.context_memory_save_payload({
                "item": {
                    "text": "ユーザーは短い箇条書きを好む",
                    "memoryType": "preference",
                    "sourceType": "manual",
                    "sourceId": "manual-1",
                },
                "scope": {"scopeType": "folder", "scopeId": "folder-1"},
            })
            updated = server.context_memory_update_payload({
                "id": saved["record"]["id"],
                "text": "ユーザーは短く具体的な箇条書きを好む",
                "memoryType": "preference",
            })
            listed = server.context_memory_list_payload({"scopeType": "folder", "scopeId": "folder-1"})
        finally:
            server.CONTEXT_DB_PATH = previous_context_db

    assert updated["ok"] is True
    assert updated["record"]["snippet"] == "ユーザーは短く具体的な箇条書きを好む"
    assert listed["records"][0]["snippet"] == "ユーザーは短く具体的な箇条書きを好む"


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


def test_ollama_http_error_event_is_stream_json_safe() -> None:
    exc = urllib.error.HTTPError(
        "http://127.0.0.1:11434/api/chat",
        404,
        "Not Found",
        {},
        BytesIO(b'{"error":"model \\"gemma4:12b\\" not found"}'),
    )
    event = server.ollama_http_error_event(exc, model="gemma4:12b")
    assert event["ok"] is False
    assert event["type"] == "error"
    assert event["status"] == 404
    assert event["model"] == "gemma4:12b"
    assert "HTTP/1.0" not in event["error"]
    assert "モデルが未取得です: gemma4:12b" in event["error"]


def test_pc_diagnostics_recommendation_levels() -> None:
    comfortable = server.pc_diagnostics_recommendation({
        "memoryGb": 32,
        "isAppleSilicon": True,
        "ollamaVersion": "0.31.1",
        "availableModels": [
            "gemma4:12b-mlx",
            "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M",
            "qwen2.5:3b",
        ],
    })
    assert comfortable["level"] == "comfortable"
    assert comfortable["label"] == "快適"
    assert comfortable["recommended"]["standard"] == "gemma4:12b-mlx"
    assert comfortable["recommended"]["coding"].startswith("hf.co/yuxinlu1/gemma-4-12B-agentic")

    heavy = server.pc_diagnostics_recommendation({
        "memoryGb": 16,
        "isAppleSilicon": False,
        "ollamaVersion": "0.31.1",
        "availableModels": ["qwen2.5:3b"],
    })
    assert heavy["level"] == "heavy"
    assert heavy["label"] == "重い"
    assert heavy["recommended"]["standard"] == "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL"
    assert "12B系" in " ".join(heavy["warnings"])

    very_heavy = server.pc_diagnostics_recommendation({
        "memoryGb": 8,
        "isAppleSilicon": False,
        "ollamaVersion": "",
        "availableModels": [],
    })
    assert very_heavy["level"] == "very-heavy"
    assert very_heavy["label"] == "激重い"
    assert very_heavy["recommended"]["standard"] == "qwen2.5:3b"


def test_pc_diagnostics_payload_shape() -> None:
    payload = server.pc_diagnostics_payload(
        available_models={"gemma4:12b-mlx", "qwen2.5:3b"},
        ollama_version="0.31.1",
    )
    assert payload["ok"] is True
    assert payload["recommendation"]["label"] in {"快適", "重い", "激重い"}
    assert "memoryGb" in payload["system"]
    assert "gpu" in payload["system"]
    assert "hasGpu" in payload["system"]
    assert "recommended" in payload["recommendation"]


def test_internet_layer_diagnostics_payload_shape() -> None:
    payload = server.internet_layer_diagnostics_payload()
    assert payload["ok"] is True
    assert payload["tool"] == "Agent-Reach"
    assert payload["status"] in {"ready", "not-installed"}
    assert payload["memoryAutoSave"] is False
    assert payload["contract"]["doctorCommand"][-1] == "doctor"
    assert payload["contract"]["schemaVersion"] == "tomos-internet-layer-result-v0.1"
    assert payload["contract"]["executionPolicy"]["autoInstall"] is False
    assert payload["contract"]["executionPolicy"]["autoSaveToMemory"] is False
    assert {"web", "github", "youtube", "rss", "sns"}.issubset(payload["channels"])
    assert payload["channels"]["sns"]["status"] == "permission-required"


def test_parse_agent_reach_doctor_output_reads_json_last_line() -> None:
    parsed = server.parse_agent_reach_doctor_output('log line\n{"ok": true, "web": true}')
    assert parsed["ok"] is True
    assert parsed["web"] is True


def test_parse_agent_reach_doctor_output_reads_text_status() -> None:
    parsed = server.parse_agent_reach_doctor_output(
        "✅ GitHub 仓库和代码\n"
        "✅ YouTube 视频和字幕\n"
        "✅ RSS/Atom 订阅源\n"
        "✅ 任意网页"
    )
    assert parsed["ok"] is True
    assert parsed["web"] is True
    assert parsed["github"] is True
    assert parsed["youtube"] is True
    assert parsed["rss"] is True


def test_agent_reach_doctor_channels_normalize_partial_status() -> None:
    channels = server.agent_reach_doctor_channels({
        "web": True,
        "github": False,
        "youtube": {"status": "ready"},
        "rss": "missing",
    })
    assert channels["web"]["status"] == "ready"
    assert channels["github"]["status"] == "missing"
    assert channels["youtube"]["status"] == "ready"
    assert channels["rss"]["status"] == "missing"
    assert channels["sns"]["status"] == "permission-required"


def test_normalize_internet_layer_channels_allows_known_channels_only() -> None:
    channels = server.normalize_internet_layer_channels(["web", "github", "v2ex", "bilibili", "bad", "web", "SNS"])
    assert channels == ["web", "github", "v2ex", "bilibili", "sns"]


def test_internet_layer_setup_status_shape() -> None:
    payload = server.internet_layer_setup_status()
    assert payload["ok"] is True
    assert "job" in payload
    assert payload["internetLayer"]["tool"] == "Agent-Reach"


def test_agent_reach_doctor_payload_reads_runner_output() -> None:
    previous = server.AGENT_REACH_COMMAND_CANDIDATES

    class FakeRunResult:
        returncode = 0
        stdout = b'{"ok": true, "web": true}\n'
        stderr = b""

    def fake_runner(*args, **kwargs):
        assert args[0][-1] == "doctor"
        return FakeRunResult()

    try:
        server.AGENT_REACH_COMMAND_CANDIDATES = ["python3"]
        payload = server.agent_reach_doctor_payload(runner=fake_runner)
    finally:
        server.AGENT_REACH_COMMAND_CANDIDATES = previous
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["doctor"]["web"] is True
    assert payload["channels"]["web"]["status"] == "ready"
    assert payload["contract"]["executionPolicy"]["autoInstall"] is False


def test_extract_youtube_urls_detects_watch_and_short_urls() -> None:
    urls = server.extract_youtube_urls(
        "この動画 https://www.youtube.com/watch?v=zfN4QApep6s と https://youtu.be/abc123 を分析"
    )
    assert urls == [
        "https://www.youtube.com/watch?v=zfN4QApep6s",
        "https://youtu.be/abc123",
    ]


def test_clean_youtube_vtt_text_removes_timestamps_and_duplicates() -> None:
    cleaned = server.clean_youtube_vtt_text(
        "WEBVTT\n\nKind: captions\nLanguage: ja\n00:00:01.000 --> 00:00:02.000\n<v Speaker>こんにちは</v>\nこんにちは\n\n2\n00:00:03.000 --> 00:00:04.000\n次の話です"
    )
    assert "WEBVTT" not in cleaned
    assert "-->" not in cleaned
    assert cleaned.splitlines() == ["こんにちは", "次の話です"]


def test_youtube_transcript_from_metadata_uses_automatic_caption_url() -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n字幕本文\n".encode("utf-8")

    def fake_opener(url, timeout=0):
        assert url == "https://example.test/caption.vtt"
        return FakeResponse()

    transcript = server.youtube_transcript_from_metadata(
        {
            "automatic_captions": {
                "ja": [
                    {"ext": "json3", "url": "https://example.test/caption.json3"},
                    {"ext": "vtt", "url": "https://example.test/caption.vtt"},
                ],
            },
        },
        opener=fake_opener,
    )
    assert transcript == "字幕本文"


def test_extract_web_urls_excludes_youtube_urls() -> None:
    urls = server.extract_web_urls(
        "https://example.com/article と https://www.youtube.com/watch?v=zfN4QApep6s と https://github.com/openai/codex"
    )
    assert urls == ["https://example.com/article"]


def test_web_reader_result_uses_jina_reader_request(monkeypatch=None) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"Title: Example Article\n\nMain body text"

    def fake_opener(request, timeout=0):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    result = server.web_reader_result("https://example.com/article", opener=fake_opener)
    assert captured["url"] == "https://r.jina.ai/https://example.com/article"
    assert captured["timeout"] == server.WEB_READER_TIMEOUT_SECONDS
    assert result is not None
    assert result["title"] == "Webページ本文: Example Article"
    assert "Main body text" in result["snippet"]


def test_should_read_search_result_pages_detects_complete_list_request() -> None:
    assert server.should_read_search_result_pages("ガンダムの全シリーズを箇条書きして")
    assert server.should_read_search_result_pages("作品一覧を出して")
    assert not server.should_read_search_result_pages("ガンダムについて教えて")


def test_augment_search_results_with_page_text_reads_first_result() -> None:
    calls = []

    def fake_reader(url):
        calls.append(url)
        return {
            "title": "Webページ本文: ガンダムシリーズ一覧",
            "url": url,
            "snippet": "Title: ガンダムシリーズ一覧\n機動戦士ガンダム\n機動戦士Ζガンダム",
            "source": "agent-reach:web",
        }

    results, error = server.augment_search_results_with_page_text(
        "ガンダムの全シリーズを箇条書きして",
        [{
            "title": "ガンダムシリーズ一覧",
            "url": "https://example.com/gundam-list",
            "snippet": "シリーズ一覧",
        }],
        reader=fake_reader,
    )
    assert error == ""
    assert calls == ["https://example.com/gundam-list"]
    assert len(results) == 2
    assert results[1]["title"] == "Webページ本文: ガンダムシリーズ一覧"


def test_augment_search_results_with_page_text_reads_multiple_prioritized_results() -> None:
    calls = []

    def fake_reader(url):
        calls.append(url)
        return {
            "title": f"Webページ本文: {url}",
            "url": url,
            "snippet": f"本文: {url}",
            "source": "agent-reach:web",
        }

    results, error = server.augment_search_results_with_page_text(
        "ガンダムの全シリーズを箇条書きして",
        [
            {"title": "個人ブログ", "url": "https://blog.example/gundam", "snippet": "感想"},
            {"title": "製作年順インデックス", "url": "https://gundam-official.com/news/i/special-series/gundam-works/01_746", "snippet": "公式一覧"},
            {"title": "ガンダムシリーズ一覧", "url": "https://ja.wikipedia.org/wiki/ガンダムシリーズ一覧", "snippet": "一覧"},
            {"title": "別ブログ", "url": "https://note.example/gundam", "snippet": "まとめ"},
        ],
        reader=fake_reader,
    )
    assert error == ""
    assert calls == [
        "https://gundam-official.com/news/i/special-series/gundam-works/01_746",
        "https://ja.wikipedia.org/wiki/ガンダムシリーズ一覧",
        "https://blog.example/gundam",
    ]
    assert len(results) == 7


def test_augment_search_results_with_page_text_follows_list_page_links() -> None:
    calls = []
    pages = {
        "https://gundam-official.com/news/i/special-series/gundam-works/01_746": (
            "機動戦士ガンダム\n"
            "[次の一覧](https://gundam-official.com/news/i/special-series/gundam-works/02_747)"
        ),
        "https://gundam-official.com/news/i/special-series/gundam-works/02_747": (
            "機動戦士Ζガンダム\n"
            "[3ページ目](https://gundam-official.com/news/i/special-series/gundam-works/03_748)"
        ),
        "https://gundam-official.com/news/i/special-series/gundam-works/03_748": "機動戦士ガンダムZZ",
    }

    def fake_reader(url):
        calls.append(url)
        return {
            "title": f"Webページ本文: {url}",
            "url": url,
            "snippet": pages[url],
            "source": "agent-reach:web",
        }

    results, error = server.augment_search_results_with_page_text(
        "ガンダムの全シリーズを箇条書きして",
        [{
            "title": "製作年順インデックス",
            "url": "https://gundam-official.com/news/i/special-series/gundam-works/01_746",
            "snippet": "公式一覧",
        }],
        reader=fake_reader,
    )
    assert error == ""
    assert calls == [
        "https://gundam-official.com/news/i/special-series/gundam-works/01_746",
    ]
    source_text = server.source_text_for_results(results)
    assert "機動戦士ガンダムZZ" not in source_text


def complete_list_page(url: str, items: list[str]) -> dict[str, str]:
    return {
        "title": "Webページ本文: シリーズ一覧",
        "url": url,
        "source": "agent-reach:web",
        "snippet": "\n".join(f"- [{item}]({url}#{index})" for index, item in enumerate(items)),
    }


def test_complete_list_evidence_prefers_more_complete_trusted_source() -> None:
    official = complete_list_page("https://official.example/works", ["星の旅人", "星の旅人Z", "星の旅人ZZ"])
    encyclopedia = complete_list_page("https://ja.wikipedia.org/wiki/星の旅人", [f"星の旅人{i}" for i in range(12)])
    evidence = server.build_complete_list_evidence("全シリーズを箇条書きして", [official, encyclopedia])
    assert evidence.source_domain == "ja.wikipedia.org"
    assert len(evidence.candidates) == 12
    assert evidence.status == "source-backed"


def test_complete_list_evidence_rejects_navigation_pages() -> None:
    results = [
        complete_list_page("https://ja.wikipedia.org/wiki/星の旅人", ["星の旅人", "星の旅人Z", "星の旅人ZZ"]),
        complete_list_page("https://ja.wikipedia.org/w/index.php?title=特別:ログイン", ["ログイン", "アカウント作成"]),
    ]
    evidence = server.build_complete_list_evidence("全シリーズを箇条書きして", results)
    assert all("ログイン" not in item for item in evidence.candidates)


def test_extract_list_followup_links_rejects_image_assets() -> None:
    links = server.extract_list_followup_links({
        "title": "Webページ本文: 製作年順インデックス",
        "url": "https://example.com/works/01_746",
        "snippet": "\n".join([
            "[次の一覧](https://example.com/works/02_747)",
            "[1st_300x300.jpg](https://example.com/works/1st_300x300.jpg)",
            "https://example.com/works/z_thum.jpg",
        ]),
    })
    assert links == ["https://example.com/works/02_747"]


def test_extract_list_followup_links_rejects_other_numeric_detail_paths() -> None:
    links = server.extract_list_followup_links({
        "title": "Webページ本文: 製作年順インデックス",
        "url": "https://example.com/special/gundam-works/01_746",
        "snippet": "\n".join([
            "[MODULE.002](https://example.com/special/gundam-works/02_747)",
            "[機動戦士ガンダム](https://example.com/works/01_001)",
            "[Gのレコンギスタ](https://example.com/works/14_026)",
        ]),
    })
    assert links == ["https://example.com/special/gundam-works/02_747"]


def test_web_reader_keeps_titles_after_legacy_24k_boundary() -> None:
    late_title = "## [後半にある作品](https://example.com/works/late)"
    body = "Title: 公式一覧\n" + ("説明文" * 9000) + "\n" + late_title

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return body.encode("utf-8")

    result = server.web_reader_result(
        "https://example.com/works",
        opener=lambda request, timeout=0: FakeResponse(),
    )
    assert result is not None
    assert late_title in result["snippet"]


def test_select_complete_list_grounding_results_prefers_one_authoritative_domain() -> None:
    official_results = [
        {
            "title": f"Webページ本文: 公式一覧 {index}",
            "url": f"https://official.example/works/{index}",
            "snippet": f"## [星の旅人{index}](https://official.example/title/{index})",
        }
        for index in range(1, 4)
    ]
    mixed_results = [
        {
            "title": "Webページ本文: 関連作品一覧",
            "url": "https://ja.wikipedia.org/wiki/星の旅人シリーズ",
            "snippet": "- ゲーム『星の旅人バトル』\n- 漫画『星の旅人外伝』",
        },
        *official_results,
    ]
    selected = server.select_complete_list_grounding_results(mixed_results)
    assert selected == official_results


def test_complete_list_search_context_excludes_other_domain_categories() -> None:
    results = [
        {
            "title": "Webページ本文: 関連作品一覧",
            "url": "https://ja.wikipedia.org/wiki/星の旅人シリーズ",
            "snippet": "- ゲーム『星の旅人バトル』\n- 漫画『星の旅人外伝』",
        },
        {
            "title": "Webページ本文: 公式一覧",
            "url": "https://official.example/works/1",
            "snippet": "\n".join([
                "## [星の旅人](https://official.example/title/1)",
                "## [星の旅人Z](https://official.example/title/2)",
                "## [星の旅人ZZ](https://official.example/title/3)",
            ]),
        },
    ]
    context = server.build_search_context_for_query("全シリーズを箇条書きして", results)
    assert "星の旅人ZZ" in context
    assert "星の旅人バトル" not in context
    assert "星の旅人外伝" not in context


def test_extract_grounded_list_candidates_rejects_fragments_and_categories() -> None:
    candidates = server.extract_grounded_list_candidates_from_results([
        {
            "title": "Webページ本文: ガンダムシリーズ一覧",
            "url": "https://example.com/gundam-list",
            "snippet": "\n".join([
                "- ガンダム",
                "- ガンダムシリーズ",
                "- 機動戦士ガンダム",
                "- 機動戦士Ζガンダム",
                "- 機動戦士ガンダム外伝 宇宙、閃光の果てに… 機動戦士ガンダム外伝 コロニーの落ちた地で…",
                "ガンダム（IP）は、映像作品です",
                "| 機動武闘伝Gガンダム | 1994 |",
            ]),
        },
    ])
    assert "機動戦士ガンダム" in candidates
    assert "機動戦士Ζガンダム" in candidates
    assert "機動武闘伝Gガンダム" in candidates
    assert "ガンダム" not in candidates
    assert "ガンダムシリーズ" not in candidates
    assert all("宇宙、閃光" not in item for item in candidates)
    assert all("映像作品" not in item for item in candidates)


def test_extract_grounded_list_candidates_reads_markdown_link_headings() -> None:
    candidates = server.extract_grounded_list_candidates_from_results([
        {
            "title": "Webページ本文: 製作年順インデックス",
            "url": "https://example.com/works",
            "snippet": "\n".join([
                "## [機動戦士ガンダム](https://example.com/works/first)",
                "【TV】全43話",
                "## [機動戦士Ζガンダム](https://example.com/works/zeta)",
                "【TV】全50話",
                "[![Image: first](https://example.com/first.jpg)](https://example.com/works/first)",
            ]),
        },
    ])
    assert candidates == ["機動戦士ガンダム", "機動戦士Ζガンダム"]


def test_complete_list_search_context_is_compact_and_keeps_linked_titles() -> None:
    long_noise = "説明文です。" * 5000
    context = server.build_search_context_for_query(
        "全シリーズを箇条書きして",
        [
            {
                "title": "Webページ本文: 公式一覧",
                "url": "https://example.com/works",
                "snippet": "\n".join([
                    "## [星の旅人](https://example.com/works/first)",
                    "【TV】全12話",
                    "## [星の旅人Z](https://example.com/works/zeta)",
                    "【TV】全24話",
                    long_noise,
                ]),
            },
        ],
    )
    assert "星の旅人" in context
    assert "星の旅人Z" in context
    assert "説明文です。説明文です。説明文です。" not in context
    assert len(context) <= server.COMPLETE_LIST_PROMPT_MAX_CHARS


def test_complete_list_grounding_instruction_separates_mixed_categories_generically() -> None:
    instruction = server.complete_list_grounding_instruction(
        "シリーズを箇条書きして",
        [{
            "title": "Webページ本文: シリーズ一覧",
            "url": "https://example.com/series",
            "snippet": "\n".join([
                "- 星の旅人 【TV】全12話",
                "- 星の旅人 劇場版",
                "- ゲーム「星の旅人バトル」",
                "- 漫画 星の旅人外伝",
                "- 小説 星の旅人ゼロ",
                "- 模型 星の旅人プラモデル",
            ]),
        }],
    )
    assert "カテゴリ分離ルール" in instruction
    assert "映像・放送・配信" in instruction
    assert "ゲーム" in instruction
    assert "書籍・漫画・小説" in instruction
    assert "商品・模型" in instruction
    assert "確認済み候補:" not in instruction
    assert "ゲーム「星の旅人バトル」" not in instruction
    assert "模型 星の旅人プラモデル" not in instruction


def test_organize_mixed_list_categories_splits_generated_bullets() -> None:
    content = "\n".join([
        "まさふみ、確認できた項目をまとめるね。",
        "",
        "## 確認できた項目",
        "- 星の旅人 【TV】全12話",
        "- ゲーム「星の旅人バトル」",
        "- 漫画 星の旅人外伝",
        "- 模型 星の旅人プラモデル",
        "",
        "## 確認できていない点",
        "- 出典本文で確認できない項目は除外しました。",
    ])
    organized = server.organize_mixed_list_categories(
        content,
        "シリーズを箇条書きして",
        [{
            "title": "Webページ本文: シリーズ一覧",
            "url": "https://example.com/series",
            "snippet": "\n".join([
                "- 星の旅人 【TV】全12話",
                "- ゲーム「星の旅人バトル」",
                "- 漫画 星の旅人外伝",
                "- 模型 星の旅人プラモデル",
            ]),
        }],
    )
    assert "まさふみ、確認できた項目をまとめるね。" in organized
    assert "### 映像・放送・配信" in organized
    assert "### ゲーム" in organized
    assert "### 書籍・漫画・小説" in organized
    assert "### 商品・模型" in organized
    assert organized.index("### 映像・放送・配信") < organized.index("- 星の旅人 【TV】全12話")
    assert organized.index("### ゲーム") < organized.index("- ゲーム「星の旅人バトル」")
    assert "## 確認できていない点" in organized


def test_organize_mixed_list_categories_drops_metadata_and_empty_category_headings() -> None:
    content = "\n".join([
        "まさふみ、確認できた項目をまとめるね。",
        "",
        "## 映像・放送・配信",
        "",
        "## ゲーム",
        "",
        "## 確認できた項目",
        "- Published Time: 2003-05-15T03:32:31Z",
        "- Markdown Content:",
        "- ## 概要",
        "- ### 日本国内",
        "- 星の旅人 【TV】全12話",
        "- ゲーム「星の旅人バトル」",
        "- 模型 星の旅人プラモデル",
        "",
        "## 確認できていない点",
        "- 出典本文で確認できない項目は除外しました。",
    ])
    organized = server.organize_mixed_list_categories(
        content,
        "シリーズを箇条書きして",
        [{
            "title": "Webページ本文: シリーズ一覧",
            "url": "https://example.com/series",
            "snippet": "\n".join([
                "Published Time: 2003-05-15T03:32:31Z",
                "Markdown Content:",
                "## 概要",
                "### 日本国内",
                "- 星の旅人 【TV】全12話",
                "- ゲーム「星の旅人バトル」",
                "- 模型 星の旅人プラモデル",
            ]),
        }],
    )
    assert "Published Time" not in organized
    assert "Markdown Content" not in organized
    assert "- ## 概要" not in organized
    assert "- ### 日本国内" not in organized
    organized_lines = organized.splitlines()
    assert "## 映像・放送・配信" not in organized_lines
    assert "## ゲーム" not in organized_lines
    assert "### 映像・放送・配信" in organized
    assert "### ゲーム" in organized
    assert "### 商品・模型" in organized
    assert "### 未分類" not in organized


def test_organize_mixed_list_categories_keeps_unclassified_titles() -> None:
    content = "\n".join([
        "まさふみ、確認できた項目をまとめるね。",
        "",
        "## 確認できた項目",
        "- 機動戦士ガンダム",
        "- 機動戦士Ζガンダム",
        "- ゲーム『ガンダムバトル』",
        "- 模型 ガンダムモデル",
    ])
    organized = server.organize_mixed_list_categories(
        content,
        "全シリーズを箇条書きして",
        [{
            "title": "Webページ本文: シリーズ一覧",
            "url": "https://example.com/series",
            "snippet": content,
        }],
    )
    assert organized == content


def test_build_search_context_blocks_unverified_list_completion() -> None:
    context = server.build_search_context([{
        "title": "ガンダムシリーズ一覧",
        "url": "https://example.com/gundam-list",
        "snippet": "シリーズ一覧",
    }])
    assert "Do not invent titles, names, dates, numbers, or list items" in context
    assert "complete list could not be confirmed" in context


def test_remove_unverified_list_items_filters_hallucinated_gundam_titles() -> None:
    content = "\n".join([
        "**宇宙世紀シリーズ**",
        "* 機動戦士ガンダム（初代）",
        "* 機動戦士ガンダム鋼の谷",
        "* 機動戦士ガンダム逆襲のシャア",
    ])
    filtered = server.remove_unverified_list_items(
        content,
        "ガンダムの全シリーズを箇条書きして",
        [{
            "title": "Webページ本文: ガンダムシリーズ一覧",
            "url": "https://example.com/gundam-list",
            "snippet": "機動戦士ガンダム\n機動戦士ガンダム 逆襲のシャア\n機動戦士Ζガンダム",
        }],
    )
    assert "機動戦士ガンダム（初代）" in filtered
    assert "機動戦士ガンダム逆襲のシャア" in filtered
    assert "機動戦士ガンダム鋼の谷" not in filtered
    assert "出典本文で確認できない項目は除外しました" in filtered


def test_complete_list_grounding_instruction_keeps_character_generation() -> None:
    instruction = server.complete_list_grounding_instruction(
        "ガンダムの全シリーズを箇条書きして",
        [{
            "title": "Webページ本文: ガンダムシリーズ一覧",
            "url": "https://example.com/gundam-list",
            "snippet": "\n".join([
                "- 機動戦士ガンダム",
                "- 機動戦士Ζガンダム",
                "- 機動戦士ガンダム 逆襲のシャア",
            ]),
        }],
    )
    assert "一覧系Web調査回答ルール" in instruction
    assert "本文に文字として明示された項目だけ" in instruction
    assert "直前のAI回答、一般知識、推測、連想で項目を増やさない" in instruction
    assert "途中で切れた断片" in instruction
    assert "通常のマイキャラの口調" in instruction
    assert "確認済み候補:" not in instruction
    assert "- 機動戦士ガンダム" not in instruction


def test_extract_github_repos_reads_owner_repo() -> None:
    repos = server.extract_github_repos("https://github.com/Panniantong/Agent-Reach と https://github.com/openai/codex")
    assert repos == ["Panniantong/Agent-Reach", "openai/codex"]


def test_github_repo_result_uses_gh_runner(monkeypatch=None) -> None:
    def fake_runner(command, **kwargs):
        assert command[:3] == ["gh", "repo", "view"]
        assert command[3] == "Panniantong/Agent-Reach"

        class FakeRunResult:
            returncode = 0
            stdout = b'{"nameWithOwner":"Panniantong/Agent-Reach","description":"Internet router","url":"https://github.com/Panniantong/Agent-Reach","stargazerCount":123,"primaryLanguage":{"name":"Python"}}'
            stderr = b""

        return FakeRunResult()

    result = server.github_repo_result("Panniantong/Agent-Reach", runner=fake_runner)
    assert result is not None
    assert result["title"] == "GitHubリポジトリ: Panniantong/Agent-Reach"
    assert "Internet router" in result["snippet"]
    assert "Python" in result["snippet"]


def test_github_search_results_uses_gh_runner(monkeypatch=None) -> None:
    def fake_runner(command, **kwargs):
        assert command[:3] == ["gh", "search", "repos"]

        class FakeRunResult:
            returncode = 0
            stdout = b'[{"fullName":"openai/codex","description":"coding agent","url":"https://github.com/openai/codex","stargazersCount":1000}]'
            stderr = b""

        return FakeRunResult()

    results = server.github_search_results("github coding agent", runner=fake_runner, limit=1)
    assert len(results) == 1
    assert results[0]["url"] == "https://github.com/openai/codex"
    assert "coding agent" in results[0]["snippet"]


def test_rss_feed_result_reads_items(monkeypatch=None) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"""<?xml version='1.0'?>
<rss><channel><title>Example Feed</title>
<item><title>First</title><link>https://example.com/1</link><description>Summary one</description></item>
<item><title>Second</title><link>https://example.com/2</link></item>
</channel></rss>"""

    def fake_opener(request, timeout=0):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    result = server.rss_feed_result("https://example.com/feed.xml", opener=fake_opener)
    assert captured["url"] == "https://example.com/feed.xml"
    assert captured["timeout"] == server.RSS_TIMEOUT_SECONDS
    assert result is not None
    assert result["title"] == "RSSフィード: Example Feed"
    assert "First" in result["snippet"]
    assert "Summary one" in result["snippet"]


def test_v2ex_hot_results_reads_public_api(monkeypatch=None) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'[{"title":"Topic","url":"https://www.v2ex.com/t/1","replies":3,"node":{"title":"Tech"},"member":{"username":"user"}}]'

    results = server.v2ex_hot_results(opener=lambda request, timeout=0: FakeResponse(), limit=1)
    assert len(results) == 1
    assert results[0]["title"] == "V2EX: Topic"
    assert "Tech" in results[0]["snippet"]


def test_bilibili_search_results_reads_video_group(monkeypatch=None) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"data":{"result":[{"result_type":"video","data":[{"title":"<em class=\\"keyword\\">AI</em> video","bvid":"BV123","author":"up","description":"desc"}]}]}}'

    results = server.bilibili_search_results("AI", opener=lambda request, timeout=0: FakeResponse(), limit=1)
    assert len(results) == 1
    assert results[0]["url"] == "https://www.bilibili.com/video/BV123"
    assert "AI video" in results[0]["snippet"]


def test_youtube_transcript_result_uses_runner_output(monkeypatch=None) -> None:
    calls = []

    class FakeRunResult:
        def __init__(self, returncode=0, stdout=b"", stderr=b""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_runner(command, **kwargs):
        calls.append(command)
        if "--dump-json" in command:
            return FakeRunResult(stdout=b'{"id":"vid123","title":"Demo Video","description":"Demo description"}\n')
        output_template = command[command.index("-o") + 1]
        subtitle_path = Path(output_template.replace("%(id)s", "vid123").replace("%(ext)s", "ja.vtt"))
        subtitle_path.write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n字幕の本文です\n",
            encoding="utf-8",
        )
        return FakeRunResult()

    previous = server.agent_reach_venv_ytdlp_command
    try:
        server.agent_reach_venv_ytdlp_command = lambda: ["python", "-m", "yt_dlp"]
        result = server.youtube_transcript_result("https://www.youtube.com/watch?v=vid123", runner=fake_runner)
    finally:
        server.agent_reach_venv_ytdlp_command = previous
    assert result is not None
    assert result["title"] == "YouTube動画: Demo Video"
    assert result["url"] == "https://www.youtube.com/watch?v=vid123"
    assert "字幕の本文です" in result["snippet"]
    assert all("--extractor-args" in command for command in calls)
    assert all("youtube:player_client=android,android_vr" in command for command in calls)
    assert any("--write-auto-sub" in command for command in calls)


def test_internet_layer_context_results_prefers_youtube_channel(monkeypatch=None) -> None:
    previous = server.youtube_transcript_result
    try:
        server.youtube_transcript_result = lambda url, runner=None: {
            "title": "YouTube動画: テスト",
            "url": url,
            "snippet": "字幕抜粋",
        }
        results, error = server.internet_layer_context_results(
            "https://www.youtube.com/watch?v=zfN4QApep6s を分析して",
            ["youtube"],
        )
    finally:
        server.youtube_transcript_result = previous
    assert error == ""
    assert len(results) == 1
    assert results[0]["url"] == "https://www.youtube.com/watch?v=zfN4QApep6s"


def test_should_auto_use_external_research_requires_url_and_intent() -> None:
    assert server.should_auto_use_external_research("https://www.youtube.com/watch?v=zfN4QApep6s この動画を分析して")
    assert server.should_auto_use_external_research("https://github.com/openai/codex を調べて")
    assert not server.should_auto_use_external_research("https://www.youtube.com/watch?v=zfN4QApep6s")
    assert not server.should_auto_use_external_research("この動画を分析して")


def test_auto_internet_layer_channels_for_query_uses_ready_channels() -> None:
    previous = server.internet_layer_diagnostics_payload
    try:
        server.internet_layer_diagnostics_payload = lambda: {
            "channels": {
                "youtube": {"status": "ready"},
                "github": {"status": "ready"},
                "web": {"status": "missing"},
            }
        }
        assert server.auto_internet_layer_channels_for_query("https://www.youtube.com/watch?v=zfN4QApep6s を分析して") == ["youtube"]
        assert server.auto_internet_layer_channels_for_query("https://github.com/openai/codex を調べて") == ["github"]
        assert server.auto_internet_layer_channels_for_query("https://example.com/article を読んで") == []
    finally:
        server.internet_layer_diagnostics_payload = previous


def test_external_research_answer_instruction_avoids_web_search_prompt() -> None:
    instruction = server.external_research_answer_instruction(
        [{
            "title": "YouTube動画: Demo",
            "url": "https://www.youtube.com/watch?v=vid123",
            "snippet": "動画タイトル: Demo",
        }],
        "YouTube字幕取得: unavailable",
    )
    assert "Web調査をONにしてください" in instruction
    assert "案内しないでください" in instruction
    assert "取得済みの出典があればその範囲で回答" in instruction


def test_direct_external_research_answer_uses_available_source() -> None:
    answer = server.direct_external_research_answer(
        "https://www.youtube.com/watch?v=vid123 この動画を分析して",
        [{
            "title": "YouTube動画: Demo",
            "url": "https://www.youtube.com/watch?v=vid123",
            "snippet": "動画タイトル: Demo",
        }],
        "YouTube字幕取得: unavailable",
    )
    assert "Web調査で確認できた範囲で分析します" in answer
    assert "動画タイトル: Demo" in answer
    assert "字幕本文を取得できていない" in answer
    assert "Web調査をON" not in answer


def test_direct_external_research_answer_defers_to_model_when_transcript_exists() -> None:
    answer = server.direct_external_research_answer(
        "https://www.youtube.com/watch?v=vid123 この動画を分析して",
        [{
            "title": "YouTube動画: Demo",
            "url": "https://www.youtube.com/watch?v=vid123",
            "snippet": "動画タイトル: Demo\n字幕抜粋: 半導体ショックについて解説します。",
        }],
        "",
    )
    assert answer == ""


def test_external_research_diagnostics_reports_youtube_transcript_status() -> None:
    success = server.external_research_diagnostics(
        "https://www.youtube.com/watch?v=vid123 この動画を分析して",
        ["youtube"],
        [{
            "title": "YouTube動画: Demo",
            "url": "https://www.youtube.com/watch?v=vid123",
            "snippet": "動画タイトル: Demo\n字幕抜粋: 半導体ショックについて解説します。",
            "source": "agent-reach:youtube",
        }],
        "",
    )
    assert success[0]["status"] == "success"
    assert "字幕本文" in success[0]["message"]

    failed = server.external_research_diagnostics(
        "https://www.youtube.com/watch?v=vid123 この動画を分析して",
        ["youtube"],
        [],
        "YouTube字幕取得: unavailable",
    )
    assert failed[0]["status"] == "error"
    assert "時間をおいて" in failed[0]["howToSucceed"]


def test_validate_model_remove_rejects_unknown_model() -> None:
    try:
        server.validate_model_remove("unknown:model")
    except ValueError as exc:
        assert "アンインストールできません" in str(exc)
    else:
        raise AssertionError("unknown model should be rejected")


def test_validate_model_remove_accepts_pullable_model() -> None:
    assert server.validate_model_remove("qwen2.5:3b") == "qwen2.5:3b"


if __name__ == "__main__":
    test_contract_pdf_import_status_payload_shape()
    test_contract_pdf_import_connection_test_payload_shape()
    test_sarashina_ocr_status_payload_shape()
    test_sarashina_compare_page_rejects_missing_path()
    test_contract_pdf_import_try_page_rejects_missing_path()
    test_contract_pdf_import_try_page_payload_preview()
    test_contract_pdf_import_try_all_pages_payload_preview()
    test_contract_pdf_import_auto_payload_prefers_pdf_text()
    test_contract_import_gap_payload_lists_unimported_pdf_and_docx()
    test_normalize_pdf_import_preview_text_removes_pdf_noise()
    test_normalize_pdf_import_preview_text_repairs_split_dates()
    test_contract_pdf_payload_from_path_accepts_pdf()
    test_clamp_pdf_page_number()
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
    test_workspace_context_uses_context_record_adapter_for_knowledge()
    test_context_memory_payloads_save_list_and_forget()
    test_context_memory_profile_payload_separates_stable_and_recent()
    test_context_memory_update_payload_updates_saved_memory()
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
    test_ollama_http_error_event_is_stream_json_safe()
    test_pc_diagnostics_recommendation_levels()
    test_pc_diagnostics_payload_shape()
    test_internet_layer_diagnostics_payload_shape()
    test_parse_agent_reach_doctor_output_reads_json_last_line()
    test_parse_agent_reach_doctor_output_reads_text_status()
    test_agent_reach_doctor_channels_normalize_partial_status()
    test_normalize_internet_layer_channels_allows_known_channels_only()
    test_internet_layer_setup_status_shape()
    test_agent_reach_doctor_payload_reads_runner_output()
    test_extract_youtube_urls_detects_watch_and_short_urls()
    test_clean_youtube_vtt_text_removes_timestamps_and_duplicates()
    test_youtube_transcript_from_metadata_uses_automatic_caption_url()
    test_extract_web_urls_excludes_youtube_urls()
    test_web_reader_result_uses_jina_reader_request()
    test_should_read_search_result_pages_detects_complete_list_request()
    test_augment_search_results_with_page_text_reads_first_result()
    test_augment_search_results_with_page_text_reads_multiple_prioritized_results()
    test_complete_list_evidence_prefers_more_complete_trusted_source()
    test_complete_list_evidence_rejects_navigation_pages()
    test_augment_search_results_with_page_text_follows_list_page_links()
    test_extract_list_followup_links_rejects_image_assets()
    test_extract_list_followup_links_rejects_other_numeric_detail_paths()
    test_web_reader_keeps_titles_after_legacy_24k_boundary()
    test_select_complete_list_grounding_results_prefers_one_authoritative_domain()
    test_complete_list_search_context_excludes_other_domain_categories()
    test_extract_grounded_list_candidates_rejects_fragments_and_categories()
    test_extract_grounded_list_candidates_reads_markdown_link_headings()
    test_complete_list_search_context_is_compact_and_keeps_linked_titles()
    test_complete_list_grounding_instruction_separates_mixed_categories_generically()
    test_organize_mixed_list_categories_splits_generated_bullets()
    test_organize_mixed_list_categories_drops_metadata_and_empty_category_headings()
    test_organize_mixed_list_categories_keeps_unclassified_titles()
    test_build_search_context_blocks_unverified_list_completion()
    test_remove_unverified_list_items_filters_hallucinated_gundam_titles()
    test_complete_list_grounding_instruction_keeps_character_generation()
    test_extract_github_repos_reads_owner_repo()
    test_github_repo_result_uses_gh_runner()
    test_github_search_results_uses_gh_runner()
    test_rss_feed_result_reads_items()
    test_v2ex_hot_results_reads_public_api()
    test_bilibili_search_results_reads_video_group()
    test_youtube_transcript_result_uses_runner_output()
    test_internet_layer_context_results_prefers_youtube_channel()
    test_should_auto_use_external_research_requires_url_and_intent()
    test_auto_internet_layer_channels_for_query_uses_ready_channels()
    test_external_research_answer_instruction_avoids_web_search_prompt()
    test_direct_external_research_answer_uses_available_source()
    test_direct_external_research_answer_defers_to_model_when_transcript_exists()
    test_external_research_diagnostics_reports_youtube_transcript_status()
    test_validate_model_remove_rejects_unknown_model()
    test_validate_model_remove_accepts_pullable_model()
    print("server helper tests passed")
