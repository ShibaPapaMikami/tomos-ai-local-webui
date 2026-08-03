#!/usr/bin/env python3
"""Fail-closed contract tests for the private unsigned Windows MSI workflow."""

from collections.abc import Iterable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-installers.yml"
PLAN = ROOT / "docs/superpowers/plans/2026-08-03-tomos-windows-free-distribution.md"
SOURCE_VERSION = "${{ steps.validate-inputs.outputs.source_version }}"

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
    branch = "codex/windows-unsigned-w1"
    assert f"--ref {branch}" in plan
    assert f"--branch {branch}" in plan


if __name__ == "__main__":
    test_current_workflow_passes_contract()
    test_all_unsafe_mutations_are_rejected()
    test_plan_contract()
    print("Windows unsigned distribution contract tests passed")
