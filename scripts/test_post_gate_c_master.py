#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs/superpowers/plans/2026-07-23-tomos-evolution-master.md"
DESIGN = ROOT / "docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md"
FREE_WINDOWS_PLAN = (
    ROOT
    / "docs/superpowers/plans/2026-08-03-tomos-windows-free-distribution.md"
)
SIGNED_WINDOWS_PLAN = (
    ROOT / "docs/superpowers/plans/2026-08-01-tomos-windows-signed-msi.md"
)
POST_GATE_PROGRAM = (
    ROOT / "docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md"
)


def require_in_order(text: str, tokens: list[str]) -> None:
    cursor = -1
    for token in tokens:
        next_cursor = text.find(token, cursor + 1)
        assert next_cursor >= 0, f"missing token: {token}"
        assert next_cursor > cursor, f"out of order: {token}"
        cursor = next_cursor


def compact(text: str) -> str:
    return "".join(text.split())


def test_post_gate_c_source_of_truth() -> None:
    master = MASTER.read_text(encoding="utf-8")
    design_reference = (
        "docs/superpowers/specs/"
        "2026-08-01-tomos-post-gate-c-program-design.md"
    )
    assert design_reference in master
    for gate in (
        "Gate R0",
        "Gate U0",
        "Gate U1",
        "Gate U2",
        "Gate U0F",
        "Gate M0",
        "Gate M1 / M2",
        "Gate W0",
        "Gate W1",
        "Gate W2",
        "Gate S0",
        "Gate D0",
        "Gate D1 / D2 / D3",
        "Gate REL0",
    ):
        assert gate in master
    assert "| Gate U1 / U2 |" not in master


def test_support_gate_ledger_order() -> None:
    master = MASTER.read_text(encoding="utf-8")
    ledger = master.split("## 進行台帳", 1)[1].split(
        "台帳の状態は", 1
    )[0]
    require_in_order(
        ledger,
        [
            "| Gate U0 | Gate R0合格版",
            "| Gate U1 | U0、M0、W0合格版",
            "| Gate U2 | Gate U1合格版",
            "| Gate U0F | U2、M2、選択済みWindows公開経路の合格版",
        ],
    )


def test_post_gate_c_phase_order() -> None:
    master = MASTER.read_text(encoding="utf-8")
    phase_order = master.split("## Phase Order", 1)[1].split(
        "## PWA資産版の進め方", 1
    )[0]
    require_in_order(
        phase_order,
        [
            "Gate C",
            "Gate R0",
            "Gate U0",
            "Gate M0",
            "Gate W0",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Free Windows lane",
            "Gate W1",
            "Gate W2",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Mac release lane",
            "Gate M1 / M2",
            "Final Mac M1 / M2",
            "Gate REL0",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Support lane",
            "Gate U1",
            "Gate U2",
            "Gate U0F",
            "Gate REL0",
        ],
    )
    require_in_order(
        phase_order,
        [
            "Product lane",
            "Gate 4",
            "Gate V0 / V1",
            "Gate E0 / E1",
        ],
    )
    require_in_order(
        phase_order,
        [
            "将来のWindows公開判断",
            "Gate S0",
            "Gate D0 / D1 / D2 / D3",
            "Gate REL0",
        ],
    )


def test_existing_detail_plans_remain_referenced() -> None:
    master = MASTER.read_text(encoding="utf-8")
    for filename in (
        "2026-07-23-tomos-markdown-skill-manager.md",
        "2026-07-23-tomos-voice-engine-evaluation-lab.md",
        "2026-07-23-tomos-model-evaluation-lab.md",
        "2026-08-03-tomos-windows-free-distribution.md",
    ):
        assert filename in master
    assert DESIGN.is_file()
    assert FREE_WINDOWS_PLAN.is_file()


def test_signed_windows_plan_is_paused_and_points_to_free_lane() -> None:
    signed_plan = compact(SIGNED_WINDOWS_PLAN.read_text(encoding="utf-8"))
    assert compact("有料のWeb直接配布を選ぶ場合だけ再開する任意経路として") in signed_plan
    assert "2026-08-03-tomos-windows-free-distribution.md" in signed_plan
    assert "D1からD3は明示再承認まで実行しない" in signed_plan


def test_post_gate_program_keeps_w0_to_w2_current_and_d0_historical() -> None:
    program = compact(POST_GATE_PROGRAM.read_text(encoding="utf-8"))
    assert compact("Gate W0からW2の未署名MSI開発・限定テスト") in program
    assert "D0からD3は必須工程から外して停止する" in program
    assert compact(
        "2026-08-01時点の履歴として保持し、現在の実装手順として実行しない"
    ) in program


def test_free_windows_plan_defines_structured_unsigned_workflow_contract() -> None:
    free_plan = FREE_WINDOWS_PLAN.read_text(encoding="utf-8")
    assert "def workflow_section(text: str) -> str:" in free_plan
    assert "def artifact_upload_sections(text: str) -> list[str]:" in free_plan
    assert "def artifact_upload_paths(section: str) -> list[str]:" in free_plan
    assert "assert len(uploads) == 1" in free_plan
    assert "upload = uploads[0]" in free_plan
    assert (
        'assert artifact_upload_paths(upload) == [\n'
        '        "dist/TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi",\n'
        '        "dist/TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.NOTICE.txt",\n'
        "    ]"
    ) in free_plan
    assert (
        'assert "TOMOS_AI-v0.8.233-windows.msi" not in upload'
    ) in free_plan
    assert "assert \"gh release\" not in text" in free_plan
    assert "assert \"push:\" not in trigger" in free_plan
    assert "assert \"tags:\" not in trigger" in free_plan


if __name__ == "__main__":
    test_post_gate_c_source_of_truth()
    test_support_gate_ledger_order()
    test_post_gate_c_phase_order()
    test_existing_detail_plans_remain_referenced()
    test_signed_windows_plan_is_paused_and_points_to_free_lane()
    test_post_gate_program_keeps_w0_to_w2_current_and_d0_historical()
    test_free_windows_plan_defines_structured_unsigned_workflow_contract()
    print("post-Gate-C master contract tests passed")
