from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contract_ledger import (
    delete_contract,
    extract_contract_candidate,
    list_contracts,
    save_contract,
)


SAMPLE_TEXT = """
業務委託契約書
株式会社サンプル（以下「甲」）と株式会社Gugenka（以下「乙」）は、次の通り契約する。
契約期間は2026年7月1日から2027年6月30日までとする。
本契約は期間満了の30日前までに書面による解約申入れがない場合、同一条件で1年間自動更新する。
支払条件は月末締め翌月末払いとする。
"""

PDF_SNIPPET_TEXT = """
秘密保持契約書​ ​ 株式会社BeBlock​（以下「委託者」）と、​株式会社Gugenka​（以下「受託者」）は、
委託者受託者間の​2026​年​ ​ ​6​ ​25​ 月 日付の業務委託契約書に基づき秘密保持契約を締結した。
了を含む）までとし、第1条、第2条、第5条、第6条及び第7条の規定は、業務委託契約終了日から3年間に​
限り効力を有するものとする。
"""


def test_extract_contract_candidate_from_text():
    candidate = extract_contract_candidate(
        folder_id="folder-1",
        source_path="sample-contract.txt",
        text=SAMPLE_TEXT,
    )
    assert candidate["folderId"] == "folder-1"
    assert candidate["sourcePath"] == "sample-contract.txt"
    assert candidate["contractName"] == "業務委託契約書"
    assert candidate["counterpartyName"] == "株式会社サンプル"
    assert candidate["startDate"] == "2026-07-01"
    assert candidate["endDate"] == "2027-06-30"
    assert candidate["autoRenew"] == "yes"
    assert candidate["noticePeriodDays"] == 30
    assert candidate["noticeDeadline"] == "2027-05-31"
    assert candidate["status"] == "needs_review"


def test_extract_contract_candidate_from_pdf_snippets():
    candidate = extract_contract_candidate(
        folder_id="folder-1",
        source_path="nda.pdf",
        text=PDF_SNIPPET_TEXT,
    )
    assert candidate["contractName"] == "秘密保持契約書"
    assert candidate["counterpartyName"] == "株式会社BeBlock"
    assert candidate["startDate"] == "2026-06-25"
    assert candidate["endDate"] == ""
    assert candidate["notes"].startswith("業務委託契約終了日から3年間")
    assert candidate["extractionJson"]["termNote"].startswith("業務委託契約終了日から3年間")
    assert candidate["status"] == "needs_review"


def test_save_list_delete_contract():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "contracts.sqlite"
        record = extract_contract_candidate("folder-1", "sample-contract.txt", SAMPLE_TEXT)
        record["extractionJson"]["sourceType"] = "ocr-experiment"
        saved = save_contract(db_path, record)
        assert saved["id"]
        assert saved["confirmed"] == 0
        assert saved["extractionJson"]["sourceType"] == "ocr-experiment"

        records = list_contracts(db_path, "folder-1")
        assert len(records) == 1
        assert records[0]["contractName"] == "業務委託契約書"
        assert records[0]["noticeDeadline"] == "2027-05-31"
        assert records[0]["extractionJson"]["sourceType"] == "ocr-experiment"

        delete_contract(db_path, saved["id"])
        assert list_contracts(db_path, "folder-1") == []


def test_save_contract_updates_same_folder_and_source_path():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "contracts.sqlite"
        first = extract_contract_candidate("folder-1", "nda.pdf", "秘密保持契約書\n株式会社BeBlock\n2026年6月25日付の業務委託契約書")
        first["notes"] = ""
        saved_first = save_contract(db_path, first)

        second = extract_contract_candidate(
            "folder-1",
            "nda.pdf",
            (
                "秘密保持契約書\n株式会社BeBlock\n2026年6月25日付の業務委託契約書\n"
                "第1条、第2条、第5条、第6条及び第7条の規定は、業務委託契約終了日から3年間に限り効力を有するものとする。"
            ),
        )
        saved_second = save_contract(db_path, second)
        records = list_contracts(db_path, "folder-1")

        assert saved_second["id"] == saved_first["id"]
        assert len(records) == 1
        assert records[0]["notes"].startswith("業務委託契約終了日から3年間")


def test_save_contract_merges_duplicate_source_path_records():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "contracts.sqlite"
        first = extract_contract_candidate("folder-1", "nda.pdf", "秘密保持契約書\n株式会社BeBlock\n2026年6月25日付の業務委託契約書")
        first["id"] = "old-1"
        first["notes"] = ""
        save_contract(db_path, first)
        second = {**first, "id": "old-2"}
        save_contract(db_path, second)

        update = extract_contract_candidate(
            "folder-1",
            "nda.pdf",
            (
                "秘密保持契約書\n株式会社BeBlock\n2026年6月25日付の業務委託契約書\n"
                "第1条、第2条、第5条、第6条及び第7条の規定は、業務委託契約終了日から3年間に限り効力を有するものとする。"
            ),
        )
        saved = save_contract(db_path, update)
        records = list_contracts(db_path, "folder-1")

        assert saved["id"] == "old-2"
        assert len(records) == 1
        assert records[0]["id"] == "old-2"
        assert records[0]["notes"].startswith("業務委託契約終了日から3年間")


if __name__ == "__main__":
    test_extract_contract_candidate_from_text()
    test_extract_contract_candidate_from_pdf_snippets()
    test_save_list_delete_contract()
    test_save_contract_updates_same_folder_and_source_path()
    test_save_contract_merges_duplicate_source_path_records()
    print("contract ledger tests passed")
