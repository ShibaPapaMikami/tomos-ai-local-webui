#!/usr/bin/env python3
"""Fail-closed contract tests for the private unsigned Windows MSI workflow."""

from collections.abc import Iterable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-installers.yml"
PLAN = ROOT / "docs/superpowers/plans/2026-08-03-tomos-windows-free-distribution.md"
SOURCE_VERSION = "${{ steps.validate-inputs.outputs.source_version }}"
APPROVED_COMMIT = "50e4068e0cffc8c1254ac3e01dbc691d860fb5f9"
APPROVED_TREE = "bb6d741e5de5526d5b1730bd28c96156b4b0448e"
IMMUTABLE_TAG = "w1-private-test-0.8.233-50e4068"
IMMUTABLE_RULESET = "tomos-w1-private-test-immutable-tags"

# Hand-derived contract. Do not generate this fixture from the workflow under test.
EXPECTED_WORKFLOW = """\
name: Build Windows installer
run-name: Build unsigned Windows test installer (${{ inputs.channel }})

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Test app version. This does not publish a Release."
        required: true
      channel:
        description: "development_unsigned or private_test_unsigned"
        required: true
        default: "development_unsigned"

jobs:
  windows-msi:
    name: Windows MSI
    runs-on: windows-2022
    steps:
      - uses: actions/checkout@v4
      - name: Install WiX Toolset
        shell: pwsh
        run: |
          dotnet tool install --global wix --version 4.0.6
          "$env:USERPROFILE\\.dotnet\\tools" | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
      - name: Validate unsigned inputs before build
        id: validate-inputs
        shell: pwsh
        env:
          REQUESTED_VERSION: ${{ inputs.version }}
          UNSIGNED_CHANNEL: ${{ inputs.channel }}
        run: |
          $sourceVersion = (Get-Content src-tauri/tauri.conf.json -Raw | ConvertFrom-Json).version
          $requestedVersion = $env:REQUESTED_VERSION
          $channel = $env:UNSIGNED_CHANNEL
          if ($requestedVersion -ne $sourceVersion) {
            throw "requested version does not match source version"
          }
          if ($channel -notin @("development_unsigned", "private_test_unsigned")) {
            throw "invalid unsigned distribution channel"
          }
          "source_version=$sourceVersion" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
      - name: Build MSI
        shell: pwsh
        run: |
          python scripts/make-windows-msi.py "${{ steps.validate-inputs.outputs.source_version }}"
      - name: Label MSI as unsigned test-only
        shell: pwsh
        env:
          SOURCE_VERSION: ${{ steps.validate-inputs.outputs.source_version }}
        run: |
          Copy-Item "dist/TOMOS_AI-v$env:SOURCE_VERSION-windows.msi" "dist/TOMOS_AI-v$env:SOURCE_VERSION-windows-UNSIGNED-TEST-ONLY.msi"
      - name: Write unsigned MSI notice
        shell: pwsh
        env:
          SOURCE_VERSION: ${{ steps.validate-inputs.outputs.source_version }}
        run: |
          @(
            "UNSIGNED"
            "TEST ONLY"
            "This installer is not a production release."
            "Do not disable Windows protection."
            "Before use, verify the Director-provided MSI SHA-256."
          ) | Set-Content -Path "dist/TOMOS_AI-v$env:SOURCE_VERSION-windows-UNSIGNED-TEST-ONLY.NOTICE.txt" -Encoding utf8
      - name: Write MSI summary
        shell: pwsh
        env:
          SOURCE_VERSION: ${{ steps.validate-inputs.outputs.source_version }}
          UNSIGNED_CHANNEL: ${{ inputs.channel }}
        run: |
          $sourceVersion = $env:SOURCE_VERSION
          $channel = $env:UNSIGNED_CHANNEL
          "## TOMOS AI v$sourceVersion unsigned test build" | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Encoding utf8 -Append
          "- Channel: $channel" | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Encoding utf8 -Append
          "- Windows artifact: TOMOS_AI-v$sourceVersion-windows-UNSIGNED-TEST-ONLY.msi" | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Encoding utf8 -Append
      - name: Upload MSI
        uses: actions/upload-artifact@v4
        with:
          name: TOMOS-AI-UNSIGNED-TEST-ONLY-${{ inputs.channel }}-${{ steps.validate-inputs.outputs.source_version }}
          path: |
            dist/TOMOS_AI-v${{ steps.validate-inputs.outputs.source_version }}-windows-UNSIGNED-TEST-ONLY.msi
            dist/TOMOS_AI-v${{ steps.validate-inputs.outputs.source_version }}-windows-UNSIGNED-TEST-ONLY.NOTICE.txt
          retention-days: 7
"""

EXPECTED_STEP_DESCRIPTORS = (
    "uses: actions/checkout@v4",
    "name: Install WiX Toolset",
    "name: Validate unsigned inputs before build",
    "name: Build MSI",
    "name: Label MSI as unsigned test-only",
    "name: Write unsigned MSI notice",
    "name: Write MSI summary",
    "name: Upload MSI",
)
FORBIDDEN_TEXT = (
    "gh release",
    "actions/create-release",
    "softprops/action-gh-release",
    "secrets.",
    "environment:",
    "signtool",
    "certificate",
)


def indented_section(text: str, header: str, indent: int) -> str:
    start = text.index(header) + len(header)
    lines = []
    for line in text[start:].splitlines():
        if line and len(line) - len(line.lstrip()) < indent:
            break
        lines.append(line)
    return "\n".join(lines)


def step_sections(text: str) -> list[tuple[str, int, str]]:
    jobs = indented_section(text, "jobs:\n", 2)
    job = indented_section(jobs, "  windows-msi:\n", 4)
    steps = indented_section(job, "    steps:\n", 6)
    starts = [
        position
        for position in range(len(steps))
        if steps.startswith("      - ", position)
    ]
    sections = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(steps)
        first_line_end = steps.index("\n", start)
        descriptor = steps[start + len("      - ") : first_line_end]
        sections.append((descriptor, start, steps[start:end]))
    return sections


def require_step(steps: list[tuple[str, int, str]], descriptor: str) -> tuple[int, str]:
    matches = [
        (position, section)
        for candidate, position, section in steps
        if candidate == descriptor
    ]
    assert len(matches) == 1, f"expected exactly one {descriptor!r} step"
    return matches[0]


def validate_workflow_contract(text: str) -> None:
    """Reject any workflow that differs from the approved exact contract."""
    assert text == EXPECTED_WORKFLOW
    assert text.splitlines().count("jobs:") == 1
    jobs = indented_section(text, "jobs:\n", 2)
    assert [
        line
        for line in jobs.splitlines()
        if line.startswith("  ") and not line.startswith("    ")
    ] == ["  windows-msi:"]

    steps = step_sections(text)
    assert tuple(descriptor for descriptor, _, _ in steps) == EXPECTED_STEP_DESCRIPTORS
    validate_position, validate = require_step(
        steps, "name: Validate unsigned inputs before build"
    )
    build_position, build = require_step(steps, "name: Build MSI")
    assert validate_position < build_position
    assert (
        'if ($channel -notin @("development_unsigned", "private_test_unsigned"))'
        in validate
    )
    assert SOURCE_VERSION in build
    notice_position, notice = require_step(steps, "name: Write unsigned MSI notice")
    assert build_position < notice_position
    notice_path = (
        'dist/TOMOS_AI-v$env:SOURCE_VERSION-windows-UNSIGNED-TEST-ONLY.NOTICE.txt'
    )
    assert notice.count("Set-Content") == 1
    assert notice_path in notice
    for required_label in (
        '"UNSIGNED"',
        '"TEST ONLY"',
        '"This installer is not a production release."',
        '"Do not disable Windows protection."',
        '"Before use, verify the Director-provided MSI SHA-256."',
    ):
        assert required_label in notice

    run_blocks = [
        step.split("run: |\n", 1)[1]
        for _, _, step in steps
        if "shell: pwsh" in step
    ]
    assert len(run_blocks) == 6
    assert all("${{ inputs." not in run for run in run_blocks)
    assert text.count("actions/upload-artifact@") == 1
    upload = require_step(steps, "name: Upload MSI")[1]
    assert "retention-days: 7" in upload
    assert upload.count("path:") == 1
    assert (
        "dist/TOMOS_AI-v"
        + SOURCE_VERSION
        + "-windows-UNSIGNED-TEST-ONLY.msi"
    ) in upload
    assert (
        "dist/TOMOS_AI-v"
        + SOURCE_VERSION
        + "-windows-UNSIGNED-TEST-ONLY.NOTICE.txt"
    ) in upload
    assert "0.8.233" not in text
    assert all(forbidden not in text for forbidden in FORBIDDEN_TEXT)


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"mutation anchor must occur once: {old!r}"
    mutated = text.replace(old, new, 1)
    assert mutated != text
    return mutated


def add_command(text: str, step_name: str, command: str) -> str:
    step = f"      - name: {step_name}\n"
    start = text.index(step)
    run = text.index("        run: |\n", start) + len("        run: |\n")
    return text[:run] + f"          {command}\n" + text[run:]


def move_validation_after_build(text: str) -> str:
    start = text.index("      - name: Validate unsigned inputs before build")
    build = text.index("      - name: Build MSI", start)
    label = text.index("      - name: Label MSI as unsigned test-only", build)
    return text[:start] + text[build:label] + text[start:build] + text[label:]


def mutation_cases() -> Iterable[tuple[str, str]]:
    text = EXPECTED_WORKFLOW
    normal_path = (
        "dist/TOMOS_AI-v" + SOURCE_VERSION + "-windows-UNSIGNED-TEST-ONLY.msi"
    )
    notice_path = normal_path.replace(".msi", ".NOTICE.txt")
    replacements = (
        ("extra push trigger", "\njobs:\n", "\n  push:\n\njobs:\n"),
        (
            "inline pull request trigger",
            "  workflow_dispatch:\n",
            "  workflow_dispatch:\n  pull_request: {}\n",
        ),
        (
            "optional version",
            "        required: true\n      channel:",
            "        required: false\n      channel:",
        ),
        (
            "extra input",
            '        default: "development_unsigned"',
            '        default: "development_unsigned"\n      extra:\n        required: true',
        ),
        (
            "missing channel gate",
            'if ($channel -notin @("development_unsigned", "private_test_unsigned"))',
            "if ($false)",
        ),
        ("public channel", '"private_test_unsigned")) {', '"public_unsigned")) {'),
        (
            "direct version interpolation",
            f'python scripts/make-windows-msi.py "{SOURCE_VERSION}"',
            'python scripts/make-windows-msi.py "${{ inputs.version }}"',
        ),
        ("old upload action", "actions/upload-artifact@v4", "actions/upload-artifact@v3"),
        ("normal MSI upload", normal_path, normal_path.replace("-UNSIGNED-TEST-ONLY", "")),
        ("notice name", notice_path, notice_path.replace(".NOTICE.txt", ".txt")),
        ("missing unsigned label", '"UNSIGNED"', '"SIGNED"'),
        ("missing test-only label", '"TEST ONLY"', '"TESTING ONLY"'),
        (
            "production release notice",
            '"This installer is not a production release."',
            '"This installer is a production release."',
        ),
        (
            "disable Windows protection notice",
            '"Do not disable Windows protection."',
            '"Disable Windows protection."',
        ),
        (
            "missing Director SHA-256 notice",
            '"Before use, verify the Director-provided MSI SHA-256."',
            '"Before use, verify the MSI checksum."',
        ),
        (
            "unlabelled artifact",
            "TOMOS-AI-UNSIGNED-TEST-ONLY",
            "TOMOS-AI-WINDOWS",
        ),
        ("long retention", "retention-days: 7", "retention-days: 30"),
        ("renamed job", "  windows-msi:\n", "  renamed-msi:\n"),
        ("floating runner", "    runs-on: windows-2022", "    runs-on: windows-latest"),
        (
            "write permissions",
            "    runs-on: windows-2022\n",
            "    runs-on: windows-2022\n    permissions: write-all\n",
        ),
        (
            "unnamed step",
            "      - name: Install WiX Toolset",
            "      - shell: pwsh\n        run: Write-Output unsafe\n"
            "      - name: Install WiX Toolset",
        ),
        (
            "extra action",
            "      - uses: actions/checkout@v4",
            "      - uses: actions/checkout@v4\n"
            "      - uses: actions/setup-python@v5",
        ),
        (
            "duplicate build step",
            "      - name: Build MSI",
            "      - name: Build MSI\n      - name: Build MSI",
        ),
    )
    for name, old, new in replacements:
        yield name, replace_once(text, old, new)

    yield "validation after build", move_validation_after_build(text)
    yield "extra upload step", text + "\n      - uses: actions/upload-artifact@v4\n"
    yield "release command", text + "\n      - run: gh release upload\n"
    yield "signing command", text + "\n      - run: signtool sign package.msi\n"
    yield "second job", text + """
  shadow-msi:
    name: Shadow MSI
    runs-on: windows-2022
    steps:
      - name: Build and upload outside the validated job
        shell: pwsh
        run: |
          python scripts/make-windows-msi.py "${{ inputs.version }}"
          Copy-Item "dist/TOMOS_AI-v${{ inputs.version }}-windows.msi" "dist/shadow.msi"
      - uses: actions/upload-artifact@v4
        with:
          name: shadow-msi
          path: dist/shadow.msi
"""

    dangerous_commands = (
        ("builder", f'python scripts/make-windows-msi.py "{SOURCE_VERSION}"'),
        ("copy", 'Copy-Item "dist/source.msi" "dist/copied.msi"'),
        ("upload", "gh api --method POST repos/example/actions/artifacts"),
        ("release", "gh api --method POST repos/example/releases"),
        ("signing", 'Set-AuthenticodeSignature -FilePath "dist/package.msi"'),
    )
    for step_name in ("Install WiX Toolset", "Validate unsigned inputs before build"):
        for command_name, command in dangerous_commands:
            yield f"{step_name}: {command_name}", add_command(text, step_name, command)

    for step_name in (
        "Build MSI",
        "Label MSI as unsigned test-only",
        "Write MSI summary",
    ):
        yield f"{step_name}: extra command", add_command(
            text, step_name, 'Write-Output "unexpected extra command"'
        )


def test_current_workflow_passes_contract() -> None:
    validate_workflow_contract(WORKFLOW.read_text(encoding="utf-8"))


def test_all_unsafe_mutations_are_rejected() -> None:
    for name, mutated in mutation_cases():
        try:
            validate_workflow_contract(mutated)
        except AssertionError:
            continue
        raise AssertionError(f"unsafe workflow mutation was accepted: {name}")


def test_plan_contract() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    required_evidence = (
        "docs/windows-release/windows-unsigned-build-evidence.md",
        "source version",
        "source commit",
        "tree",
        "run ID",
        "artifact name",
        "size",
        "SHA-256",
        "M0 v1 0.8.234 manifest",
        "W1 private-test",
        "記録しない",
    )
    assert all(item in plan for item in required_evidence)


def task4_section(plan: str) -> str:
    start = plan.index("### Task 4:")
    end = plan.index("### Task 5:", start)
    return plan[start:end]


def test_plan_rejects_movable_branch_ref_before_dispatch() -> None:
    """Catch a dispatch edit that runs a branch moved after approval."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    dispatch = task4[task4.index("**Step 5:") : task4.index("**Step 6:")]
    assert f"実行ref `{IMMUTABLE_TAG}`" in task4
    assert "refs/tags/$TOMOS_EXECUTION_TAG" in task4
    assert "$TOMOS_EXECUTION_TAG^{commit}" in task4
    assert APPROVED_COMMIT in task4
    assert APPROVED_TREE in task4
    assert IMMUTABLE_RULESET in task4
    assert "restrict updates" in task4
    assert "restrict deletions" in task4
    assert "bypass actorなし" in task4
    assert "Actions承認とは別の明示承認" in task4
    assert f'"ref":"{IMMUTABLE_TAG}"' in dispatch
    assert "codex/windows-unsigned-w1-task3" not in dispatch


def test_plan_stops_before_dispatch_or_artifact_follow_up_on_gate_failure() -> None:
    """Catch a shell edit that continues from a failed source or metadata gate."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    step3_start = task4.index("**Step 3:")
    step4_start = task4.index("**Step 4:", step3_start)
    step5_start = task4.index("**Step 5:", step4_start)
    step6_start = task4.index("**Step 6:", step5_start)
    step3 = task4[step3_start:step4_start]
    step5 = task4[step5_start:step6_start]
    step6 = task4[step6_start:task4.index("**Step 7:", step6_start)]
    assert "bash -euo pipefail" in step3
    assert "bash -euo pipefail" in step5
    assert "bash -euo pipefail" in step6
    assert "--method POST" in step5
    assert "jq -e" in step6
    assert "jq -er" in step6


def test_plan_accepts_only_the_exact_successful_rest_dispatched_run() -> None:
    """Catch a run-selection edit that accepts a failed or different workflow run."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    assert "actions/workflows/300666658/dispatches" in task4
    assert "X-GitHub-Api-Version: 2026-03-10" in task4
    assert "gh workflow run" not in task4
    assert (
        "--json databaseId,url,status,conclusion,headBranch,headSha,event,workflowName,createdAt"
        in task4
    )
    for assertion in (
        "databaseId == $run_id",
        'status == "completed"',
        'conclusion == "success"',
        f'headBranch == "{IMMUTABLE_TAG}"',
        f'headSha == "{APPROVED_COMMIT}"',
        'event == "workflow_dispatch"',
        'workflowName == "Build Windows installer"',
        "https://github.com/ShibaPapaMikami/tomos-ai-local-webui/actions/runs/",
    ):
        assert assertion in task4


def validate_task4_safety_contract(task4: str) -> None:
    """Validate the operator-visible gates that prevent an unsafe W1 run."""
    step3_start = task4.index("**Step 3:")
    step4_start = task4.index("**Step 4:", step3_start)
    step5_start = task4.index("**Step 5:", step4_start)
    step6_start = task4.index("**Step 6:", step5_start)
    step7_start = task4.index("**Step 7:", step6_start)
    step8_start = task4.index("**Step 8:", step7_start)
    step3 = task4[step3_start:step4_start]
    step5 = task4[step5_start:step6_start]
    step6 = task4[step6_start:step7_start]
    step7 = task4[step7_start:step8_start]
    step8 = task4[step8_start:]

    for token in (
        f"workflow source tree `{APPROVED_TREE}`",
        "Actions承認とは別の明示承認",
        "pre-notice commit `b3625373e6f0e71d9e1d0c1f175f4c10636d793f`は使用しない",
        "GitHub Releaseへ添付せず、公開URLを作らない",
    ):
        assert token in task4
    assert "archive_download_url" in task4
    assert "保存、表示、公開しない" in task4
    assert "bash -euo pipefail" in step3
    for token in (
        "bash -euo pipefail",
        'git fetch origin "refs/tags/$TOMOS_EXECUTION_TAG:refs/tags/$TOMOS_EXECUTION_TAG"',
        'test "$(git cat-file -t "refs/tags/$TOMOS_EXECUTION_TAG")" = "commit"',
        'test "$(git rev-parse "refs/tags/$TOMOS_EXECUTION_TAG^{commit}")" = "$TOMOS_APPROVED_COMMIT"',
        'test "$(git rev-parse "refs/tags/$TOMOS_EXECUTION_TAG^{tree}")" = "$TOMOS_APPROVED_TREE"',
        "actions/workflows/300666658/dispatches",
        "X-GitHub-Api-Version: 2026-03-10",
        f'"ref":"{IMMUTABLE_TAG}"',
        f'"version":"0.8.233"',
        '"channel":"private_test_unsigned"',
    ):
        assert token in step5
    for token in (
        "bash -euo pipefail",
        "databaseId == $run_id",
        'status == "completed"',
        'conclusion == "success"',
        f'headBranch == "{IMMUTABLE_TAG}"',
        f'headSha == "{APPROVED_COMMIT}"',
        'event == "workflow_dispatch"',
        'workflowName == "Build Windows installer"',
        "total_count == 1",
        "(.artifacts | length) == 1",
        'name == "TOMOS-AI-UNSIGNED-TEST-ONLY-private_test_unsigned-0.8.233"',
        "expired == false",
        "size_in_bytes <= 10485760",
        "jq -er '.artifacts[0].id",
    ):
        assert token in step6
    assert "artifact downloadの別承認" in step7
    for token in (
        "MSI `TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi`",
        "notice `TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.NOTICE.txt`",
        "だけであることを確認する",
    ):
        assert token in step8


def test_task4_safety_contract_rejects_realistic_regressions() -> None:
    """Catch removal of immutable-ref, fail-fast, metadata, or download gates."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    validate_task4_safety_contract(task4)
    mutations = (
        ("movable dispatch ref", f'"ref":"{IMMUTABLE_TAG}"', '"ref":"main"'),
        ("non-fail-fast shell", "bash -euo pipefail", "bash"),
        ("larger artifact cap", "size_in_bytes <= 10485760", "size_in_bytes <= 10485761"),
        ("missing success conclusion", 'conclusion == "success"', 'conclusion == "failure"'),
        ("download approval removed", "artifact downloadの別承認", "artifact download"),
    )
    for name, old, new in mutations:
        assert old in task4, f"mutation anchor missing: {old!r}"
        mutated = task4.replace(old, new, 1)
        try:
            validate_task4_safety_contract(mutated)
        except AssertionError:
            continue
        raise AssertionError(f"unsafe Task 4 mutation was accepted: {name}")


def test_plan_uses_the_verified_200_dispatch_response_as_the_run_id_source() -> None:
    """Catch fallback to a guessed run list or a non-authoritative 204 response."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    assert "HTTP 200" in task4
    assert "workflow_run_id" in task4
    assert "run_url" in task4
    assert "html_url" in task4
    assert "TOMOS_DISPATCH_RESPONSE" in task4
    assert "TOMOS_RUN_ID" in task4
    assert "https://api.github.com/repos/ShibaPapaMikami/tomos-ai-local-webui/actions/runs/" in task4
    assert "TOMOS_PRE_DISPATCH_RUN_IDS" not in task4
    assert "TOMOS_DISPATCH_UTC" not in task4
    assert "gh run list" not in task4
    assert "--include" not in task4
    assert "204" not in task4
    assert "type == \"array\" and length == 0" in task4

    source_readback = task4.index("**Step 1: source branchと現況をread-only確認する**")
    create_gate = task4.index("**Step 2: immutable tagとruleset作成の別承認で停止する**")
    immutable_readback = task4.index("**Step 3: 作成後のimmutable tagとrulesetをreadbackする**")
    actions_gate = task4.index("**Step 4: Actions実行の個別承認で停止する**")
    dispatch = task4.index("**Step 5: 承認後だけREST dispatchを実行する**")
    metadata = task4.index("**Step 6: runとartifactをread-only確認する**")
    assert source_readback < create_gate < immutable_readback < actions_gate < dispatch < metadata


def test_dispatch_response_contract_rejects_legacy_and_null_bypass_regressions() -> None:
    """Catch reintroduction of 204, guessed runs, invalid ordering, or null bypass."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))

    def validate(text: str) -> None:
        assert "HTTP 200" in text
        assert "204" not in text
        assert "gh run list" not in text
        assert "TOMOS_PRE_DISPATCH_RUN_IDS" not in text
        assert "TOMOS_DISPATCH_UTC" not in text
        assert text.count('type == "array" and length == 0') == 2
        assert text.index("**Step 1: source branchと現況をread-only確認する**") < text.index(
            "**Step 2: immutable tagとruleset作成の別承認で停止する**"
        ) < text.index("**Step 3: 作成後のimmutable tagとrulesetをreadbackする**") < text.index(
            "**Step 4: Actions実行の個別承認で停止する**"
        ) < text.index("**Step 5: 承認後だけREST dispatchを実行する**")

    validate(task4)
    step2 = "**Step 2: immutable tagとruleset作成の別承認で停止する**"
    step3 = "**Step 3: 作成後のimmutable tagとrulesetをreadbackする**"
    swapped_order = task4.replace(step2, "__STEP_TWO__", 1).replace(step3, step2, 1).replace(
        "__STEP_TWO__", step3, 1
    )
    mutations = (
        ("legacy 204", "HTTP 200", "HTTP 204"),
        ("run-list guessing", "TOMOS_RUN_ID", "gh run list; TOMOS_RUN_ID"),
        ("null bypass accepted", 'type == "array" and length == 0', "length == 0"),
        ("tag creation after readback", task4, swapped_order),
    )
    for name, old, new in mutations:
        if name == "tag creation after readback":
            mutated = new
        else:
            assert old in task4, f"mutation anchor missing: {old!r}"
            mutated = task4.replace(old, new, 1)
        try:
            validate(mutated)
        except (AssertionError, ValueError):
            continue
        raise AssertionError(f"unsafe dispatch response mutation was accepted: {name}")


def test_dispatch_rechecks_the_immutable_ruleset_immediately_before_post() -> None:
    """Catch a ruleset change during the Actions-approval wait before dispatch."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    step5 = task4[task4.index("**Step 5:") : task4.index("**Step 6:")]

    def validate(text: str) -> None:
        for token in (
            "TOMOS_RULESET_NAME",
            "expected exactly one active tag ruleset",
            '.name == "tomos-w1-private-test-immutable-tags"',
            '.target == "tag"',
            '.enforcement == "active"',
            '.conditions.ref_name.include == [$tag]',
            'index("update")',
            'index("deletion")',
            'type == "array" and length == 0',
            "--method POST",
        ):
            assert token in text
        assert text.count('.enforcement == "active"') == 2
        assert text.index('type == "array" and length == 0') < text.index("--method POST")

    validate(step5)
    mutations = (
        (
            "ruleset identity changed",
            '.name == "tomos-w1-private-test-immutable-tags"',
            '.name == "another-ruleset"',
        ),
        ("ruleset disabled", '.enforcement == "active"', '.enforcement == "disabled"'),
        ("null bypass accepted", 'type == "array" and length == 0', "length == 0"),
        ("post before ruleset", "--method POST", "__POST__"),
    )
    for name, old, new in mutations:
        assert old in step5, f"mutation anchor missing: {old!r}"
        mutated = step5.replace(old, new, 1)
        if name == "post before ruleset":
            mutated = mutated.replace('type == "array" and length == 0', "--method POST", 1)
        try:
            validate(mutated)
        except AssertionError:
            continue
        raise AssertionError(f"unsafe pre-dispatch ruleset mutation was accepted: {name}")


def test_task4_contract_rejects_missing_step5_tag_identity_checks() -> None:
    """Catch a dispatch edit that drops tag identity checks after approval waits."""
    task4 = task4_section(PLAN.read_text(encoding="utf-8"))
    mutations = (
        (
            "tag fetch",
            'git fetch origin "refs/tags/$TOMOS_EXECUTION_TAG:refs/tags/$TOMOS_EXECUTION_TAG"',
        ),
        (
            "tag object type",
            'test "$(git cat-file -t "refs/tags/$TOMOS_EXECUTION_TAG")" = "commit"',
        ),
        (
            "approved commit",
            'test "$(git rev-parse "refs/tags/$TOMOS_EXECUTION_TAG^{commit}")" = "$TOMOS_APPROVED_COMMIT"',
        ),
        (
            "approved tree",
            'test "$(git rev-parse "refs/tags/$TOMOS_EXECUTION_TAG^{tree}")" = "$TOMOS_APPROVED_TREE"',
        ),
    )
    for name, token in mutations:
        assert task4.count(token) == 2, f"unexpected mutation anchor count: {name}"
        first = task4.index(token)
        second = task4.index(token, first + len(token))
        mutated = task4[:second] + task4[second + len(token) :]
        try:
            validate_task4_safety_contract(mutated)
        except AssertionError:
            continue
        raise AssertionError(f"unsafe Step 5 tag identity mutation was accepted: {name}")


if __name__ == "__main__":
    test_current_workflow_passes_contract()
    test_all_unsafe_mutations_are_rejected()
    test_plan_contract()
    test_plan_rejects_movable_branch_ref_before_dispatch()
    test_plan_stops_before_dispatch_or_artifact_follow_up_on_gate_failure()
    test_plan_accepts_only_the_exact_successful_rest_dispatched_run()
    test_task4_safety_contract_rejects_realistic_regressions()
    test_plan_uses_the_verified_200_dispatch_response_as_the_run_id_source()
    test_dispatch_response_contract_rejects_legacy_and_null_bypass_regressions()
    test_dispatch_rechecks_the_immutable_ruleset_immediately_before_post()
    test_task4_contract_rejects_missing_step5_tag_identity_checks()
    print("Windows unsigned distribution contract tests passed")
