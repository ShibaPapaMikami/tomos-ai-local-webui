# TOMOS Windows署名MSI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固定供給値、再現可能なMSI identity、安全なWindows runtime、署名CIを実装し、D1の署名済みWindows x64 MSI候補を作れる状態にする。

**Architecture:** Task 4で承認済みのM0 schema contractを先に利用し、Windows供給値を外部readback後にlockする。供給検証、path / migration、MSI packaging、署名CIを独立したfail-closed componentに分け、unsigned testとsecretを使うsigning jobを分離する。D1では自動・静的検証までを担当し、install、uninstall、第三者試験はD2 / D3へ渡す。

**Tech Stack:** Python 3.11標準ライブラリ、Rust / Tauri 2、WiX MSI、PowerShell、GitHub Actions、Authenticode SHA-256、RFC 3161。

## Global Constraints

- Ownerはエンジニア2。一つのTaskでshared fileを変更するownerは一人だけにする。
- EntryはD0設計承認と、Task 4で承認済みのM0 schema / validator contract。
- 対象architectureはWindows x64。Product名はASCIIの`TOMOS AI`。
- stable UpgradeCodeは`7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1`。
- ProductCode UUIDv5 namespaceは`C3C54504-8F05-5B59-AB5E-14E70A734EB8`。
- ProductCode入力は`TOMOS AI|x64|0.8.234`の形式とし、versionは先頭`v`なしのSemVer。
- install先は`%ProgramFiles%\ShibaPapa Studio\TOMOS AI`。
- data先は`%LOCALAPPDATA%\ShibaPapa Studio\TOMOS AI`。
- exe / dllを先に署名し、MSIを最後に署名する。
- digestとRFC 3161 timestamp digestはSHA-256を使う。
- PR、fork、通常pushではunsigned testだけを実行する。
- signingは`workflow_dispatch`、protected Environment、required reviewerを必須にする。
- tag pushだけで署名・公開を開始しない。
- Release buildはPATH上のPythonやオンラインWebView2取得へfallbackしない。
- uninstallでMemory、Knowledge、教材、設定、chat、modelを削除しない。
- current v0.8.233 PKG / sourceをv0.8.234 Windows成果物として再利用しない。
- secret、token、user名、full path、会話、Memory、Knowledgeをlog / artifactへ出さない。
- certificate、timestamp、runtime、WebView2、dependency、secret、workflow、build、署名、
  実機、commit、pushはそれぞれ実行前に個別承認を得る。
- 未確定のcertificate / runtime / WebView2値を推測しない。承認済みreadbackまで停止する。

---

## Required Execution Order and Ownership Handoff

```text
M0 Task 1〜4: schema / validator contract
  → Windows Task 1〜4: supply、identity / path、staging、migration
  → D0 supply承認
  → M0 Task 5〜8: version 0.8.234 / source-lock
  → M0 ownerからDirectorを介した明示handoff
  → Windows Task 5〜7: MSI bundle、signing、D1 Gate
```

- Windows Task 1〜4はM0 shared fileを変更しない。
- M0 Task 8完了まで、`src-tauri/tauri.conf.json`、`src-tauri/Cargo.toml`、
  `src-tauri/Cargo.lock`、`scripts/make-windows-msi.py`のownerはM0。
- M0 ownerはTask 8完了時にversion、source commit、tree、clean状態、
  `docs/releases/windows-source-manifest.json`のSHA、shared file一覧をDirectorへ返す。
- Directorは値をreadbackし、同じsource-lockからD1専用worktreeを作り、上記4 shared
  fileのownerをエンジニア2へ移す。口頭推測だけで移管しない。
- `scripts/release_manifest.py`、`scripts/test_release_manifest.py`、
  `docs/releases/`はM0 ownerのままとし、Windows Task 5〜7はread-onlyでconsumeする。
- handoff前、source commit / tree / manifest SHA不一致、dirty worktreeのいずれかなら
  Windows Task 5を開始しない。

---

## File and Ownership Map

| Unit | Files | Responsibility |
| --- | --- | --- |
| Supply lock | `scripts/windows_supply_lock.py`、`scripts/test_windows_supply_lock.py`、`docs/windows-release/windows-supply-lock.json`、`docs/windows-release/windows-supply-evidence.md`、`docs/windows-release/upgrade-code-evidence.md` | certificate、timestamp、Python、WebView2、過去UpgradeCodeの実在供給値とevidence |
| MSI identity / path | `scripts/windows_msi_contract.py`、`scripts/test_windows_msi_contract.py`、`app_paths.py`、`scripts/test_app_paths.py` | ProductCode、install / data path、fail-closed判定 |
| Runtime staging | `scripts/stage-windows-runtime.py`、`scripts/test_stage_windows_runtime.py` | archive検証、安全な展開、x64 / license確認 |
| Data migration characterization | Modify: `scripts/test_migration_manager.py`。Read-only: `migration_manager.py` | Windows fixtureで既存generic migrationを証明。GREEN時はproduction no-op |
| Tauri / MSI | M0 handoff後だけ`src-tauri/tauri.conf.json`、`src-tauri/Cargo.toml`、`src-tauri/Cargo.lock`、`scripts/make-windows-msi.py`、`scripts/test_windows_msi_bundle.py` | MSI bundle、resource allowlist、version / identity整合 |
| Signing gate | `scripts/verify-windows-signature.ps1`、`scripts/windows_signed_candidate.py`、`scripts/test_windows_signing_contract.py`、`.github/workflows/windows-signed-msi.yml` | unsigned CI、no-secret preflight、secret境界、署名順、candidate検証 |
| Release evidence | Read-only: `docs/releases/windows-source-manifest.json`。Create: `docs/windows-release/signed-candidate-evidence.json`、`docs/windows-release/environment-reviewer-evidence.md` | M0 source-lockのconsumeとD2/D3向けsigned candidate証跡 |

`server.py`、Web UI、Skill、Voice、Memory、Plugin、Modelは変更しない。D2 / D3の
実機試験文書とRelease公開workflowも本計画では作らない。

拒否物は`dist/rejected/windows/`だけへ隔離する。このrootはcandidate glob
`dist/candidates/windows/*.msi`と一致させず、非公開、実行禁止、CI upload対象外とする。
保持期限は30日を上限として記録するが自動削除しない。削除時は対象、size、SHA、
復旧不能範囲を示して別承認を得る。

### Test helper contract

各Python test fileは標準ライブラリだけを使い、次のhelperをtest file内に定義する。

```python
@contextmanager
def assert_raises_code(expected: str) -> Iterator[None]:
    try:
        yield
    except ContractError as error:
        assert error.code == expected, (error.code, expected)
    else:
        raise AssertionError(f"expected ContractError: {expected}")
```

新規`windows_supply_lock.py`、`windows_msi_contract.py`、
`windows_signed_candidate.py`だけが`ContractError(code: str)`を公開する。
`app_paths.py`は既存`ValueError`、`migration_manager.py`は既存`MigrationError`
subclass契約を維持する。それぞれの既存test helperを使い、新例外へ一括置換しない。
fixture builderは実在供給値と混同しない予約domain`fixture.invalid`とsynthetic
bytesだけを使う。

---

### Task 1: Windows供給lockのschemaと外部readback境界を実装する

**Files:**
- Create: `scripts/windows_supply_lock.py`
- Create: `scripts/test_windows_supply_lock.py`
- Create after approved readback: `docs/windows-release/windows-supply-lock.json`
- Create after approved readback: `docs/windows-release/windows-supply-evidence.md`
- Create after approved readback: `docs/windows-release/upgrade-code-evidence.md`
- Read: `scripts/release_manifest.py`
- Read: `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`

**Interfaces:**
- Consumes: Task 4承認済みM0 schema contract
- Produces: `WindowsSupplyLock`、`load_windows_supply_lock(path: Path) -> WindowsSupplyLock`、`validate_windows_supply_lock(raw: Mapping[str, object]) -> WindowsSupplyLock`

供給lockのexact key set:

```python
REQUIRED_KEYS = {
    "schema_version",
    "architecture",
    "certificate",
    "timestamp",
    "python_runtime",
    "webview2",
}
```

`certificate`はprovider、subject、issuer、fingerprint、key_identity、valid_from、
valid_until、storage_kindを持つ。`timestamp`はrfc3161_urlとdigestを持つ。
Python / WebView2はsource、version、artifact_name、url、size、sha256、license_name、
license_url、license_sha256を持つ。

```python
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


@dataclass(frozen=True)
class TimestampLock:
    rfc3161_url: str
    digest: str


@dataclass(frozen=True)
class WindowsSupplyLock:
    schema_version: int
    architecture: str
    certificate: CertificateLock
    timestamp: TimestampLock
    python_runtime: SupplyArtifact
    webview2: SupplyArtifact
```

`scripts/test_windows_supply_lock.py`は次のsynthetic fixture builderを定義する。

```python
def valid_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "architecture": "x64",
        "certificate": {
            "provider": "fixture-provider",
            "subject": "CN=TOMOS Fixture",
            "issuer": "CN=Fixture Issuer",
            "fingerprint": "A" * 64,
            "key_identity": "fixture-key",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z",
            "storage_kind": "fixture-only",
        },
        "timestamp": {
            "rfc3161_url": "https://timestamp.fixture.invalid/rfc3161",
            "digest": "sha256",
        },
        "python_runtime": supply_fixture("python-runtime.zip", "B" * 64),
        "webview2": supply_fixture("webview2-offline.exe", "C" * 64),
    }
```

`supply_fixture(name, sha256)`も同test file内に定義し、size `1024`、license SHA
`"D" * 64`、supported architecture `x64`、
`https://download.fixture.invalid/`だけを返す。

- [ ] **Step 1: generic fixtureだけで失敗testを書く**

```python
def test_supply_lock_rejects_unknown_key() -> None:
    raw = valid_fixture()
    raw["unexpected"] = True
    with assert_raises_code("unknown_field"):
        validate_windows_supply_lock(raw)


def test_supply_lock_requires_x64_and_sha256() -> None:
    raw = valid_fixture()
    raw["architecture"] = "arm64"
    with assert_raises_code("unsupported_architecture"):
        validate_windows_supply_lock(raw)
```

- [ ] **Step 2: REDを確認する**

Run:

```bash
python3 scripts/test_windows_supply_lock.py
```

Expected: FAIL with `ModuleNotFoundError: windows_supply_lock`。

- [ ] **Step 3: 標準ライブラリだけでvalidatorを実装する**

```python
def validate_windows_supply_lock(
    raw: Mapping[str, object],
) -> WindowsSupplyLock:
    require_exact_keys(raw, REQUIRED_KEYS)
    require_architecture(raw["architecture"])
    return WindowsSupplyLock.from_mapping(raw)
```

Duplicate JSON key、unknown field、不正型、空文字、非HTTPS URL、非正size、64桁でない
SHA、`digest != "sha256"`を固定error codeで拒否する。certificate / URL実値は
generic fixtureへ入れず、test専用synthetic valueを明示する。
`require_exact_keys`は`set(raw) == expected`を検査し、欠落を`missing_field`、追加を
`unknown_field`で拒否する。`require_architecture`は`x64`以外を
`unsupported_architecture`で拒否する。
`from_mapping`は各nested mappingもexact key setで検査して上記dataclassへ変換する。

- [ ] **Step 4: GREENと構文を確認する**

Run:

```bash
python3 scripts/test_windows_supply_lock.py
python3 -m py_compile scripts/windows_supply_lock.py scripts/test_windows_supply_lock.py
```

Expected: 全test pass、exit 0。

- [ ] **Step 5: 外部readbackの個別承認で停止する**

Directorは次を別々に提示し、各操作の承認を得る。

1. certificate provider / subject / issuer / fingerprint / key保管方式のreadback。
2. RFC 3161 HTTPS timestamp URLのreadback。
3. Windows x64 Python runtimeのsource / license / size / SHAのreadback。
4. WebView2 x64 offline installerのsource / license / size / SHAのreadback。
5. 現行WiX sourceと配布済みWindows MSIのUpgradeCode readback。

外部アクセスは承認前に行わない。readback結果が揃うまでrelease用
`windows-supply-lock.json`を作らず、D0を`検証中`のまま維持する。配布済みMSIが
ローカルにない場合は、取得元、artifact名、SHA、保存先を示して外部取得の個別承認を
得る。現行WiXと配布済みMSIのUpgradeCodeがどちらも
`7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1`と一致するまでTask 2とTask 5を開始しない。

- [ ] **Step 6: 承認済みevidenceからlockを作り検証する**

Run:

```bash
python3 scripts/windows_supply_lock.py \
  --lock docs/windows-release/windows-supply-lock.json \
  --evidence docs/windows-release/windows-supply-evidence.md \
  --upgrade-code-evidence docs/windows-release/upgrade-code-evidence.md
```

Expected: `windows supply lock valid`。commandはdownload、secret access、署名を行わない。

- [ ] **Step 7: commit stop**

```bash
git add \
  scripts/windows_supply_lock.py \
  scripts/test_windows_supply_lock.py \
  docs/windows-release/windows-supply-lock.json \
  docs/windows-release/windows-supply-evidence.md \
  docs/windows-release/upgrade-code-evidence.md
git diff --cached --check
```

Expected: supply unitだけstaged。ユーザーのcommit承認がある場合だけ
`git commit -m "feat: lock Windows release supplies"`を実行する。

---

### Task 2: ProductCodeとWindows pathをfail closedにする

**Files:**
- Create: `scripts/windows_msi_contract.py`
- Create: `scripts/test_windows_msi_contract.py`
- Modify: `app_paths.py`
- Modify: `scripts/test_app_paths.py`

**Interfaces:**
- Consumes: version `0.8.234`、architecture `x64`
- Produces: `product_code(version: str, architecture: str) -> str`、`windows_install_root(env: Mapping[str, str]) -> PureWindowsPath`、`windows_data_root(env: Mapping[str, str]) -> PureWindowsPath`、production `tomos_data_root()`のWindows分岐

- [ ] **Step 1: deterministic identityの失敗testを書く**

```python
def test_product_code_is_deterministic() -> None:
    expected = product_code("0.8.234", "x64")
    assert expected == product_code("0.8.234", "X64")
    assert expected == "{444BB5BB-4297-5DC1-B2BC-590D7694BCD5}"


def test_product_code_changes_with_version() -> None:
    assert product_code("0.8.234", "x64") != product_code("0.8.235", "x64")
```

固定namespace、`TOMOS AI|x64|0.8.234`、大文字・波括弧付き出力を検査する。

- [ ] **Step 2: pathの失敗testを書く**

```python
def test_data_root_uses_local_app_data() -> None:
    env = {"LOCALAPPDATA": r"C:\Users\fixture\AppData\Local"}
    result = windows_data_root(env)
    assert result == PureWindowsPath(
        r"C:\Users\fixture\AppData\Local\ShibaPapa Studio\TOMOS AI"
    )


def test_data_root_rejects_relative_root() -> None:
    with assert_raises_code("invalid_local_app_data"):
        windows_data_root({"LOCALAPPDATA": r"relative\data"})
```

missing、relative、install root内、reparse escapeを拒否するtestを追加する。

- [ ] **Step 3: REDを確認する**

Run:

```bash
python3 scripts/test_windows_msi_contract.py
python3 scripts/test_app_paths.py
```

Expected: 新interface未定義でFAIL。

- [ ] **Step 4: 最小実装を書く**

```python
PRODUCT_CODE_NAMESPACE = UUID("c3c54504-8f05-5b59-ab5e-14e70a734eb8")
UPGRADE_CODE = "7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1"


def product_code(version: str, architecture: str) -> str:
    normalized_arch = architecture.strip().lower()
    normalized_version = normalize_semver(version)
    name = f"TOMOS AI|{normalized_arch}|{normalized_version}"
    return "{" + str(uuid5(PRODUCT_CODE_NAMESPACE, name)).upper() + "}"
```

Windows pathは環境変数の値をlogへ出さず、固定error codeだけを返す。
`normalize_semver`は`re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)`
だけを許可し、先頭`v`、空白、prerelease、build metadataを`invalid_version`で拒否する。
architectureは`x64`以外を`unsupported_architecture`で拒否する。
Windows pathの構文判定には`PureWindowsPath`と`ntpath`を使い、macOSの`Path`判定へ
依存しない。

- [ ] **Step 5: production data rootへ接続する**

`app_paths.py::tomos_data_root()`の既存override優先順位を維持し、Windowsかつoverride
なしの場合だけ`windows_data_root(os.environ)`を返す。macOS / Linux分岐と既存
`ValueError`契約を変更しない。Windows path不正時も既存`ValueError`のcode付き
subclassを追加するだけにし、`ContractError`へ置換しない。

`scripts/test_app_paths.py`はproduction `tomos_data_root()`をWindows platform fixtureで
呼び、LOCALAPPDATAのexact path、override優先、macOS既存path、missing / relative /
install-root内 / reparse escapeを検査する。

- [ ] **Step 6: GREENを確認する**

Run:

```bash
python3 scripts/test_windows_msi_contract.py
python3 scripts/test_app_paths.py
python3 -m py_compile scripts/windows_msi_contract.py app_paths.py
```

Expected: 全test pass。

- [ ] **Step 7: commit stop**

`git add`後にstaged fileがTask 2だけであることを確認し、明示承認がある場合だけ
`git commit -m "feat: define Windows MSI identity and paths"`を実行する。

---

### Task 3: Python runtimeとWebView2を安全に検証・stageする

**Files:**
- Create: `scripts/stage-windows-runtime.py`
- Create: `scripts/test_stage_windows_runtime.py`
- Read: `docs/windows-release/windows-supply-lock.json`

**Interfaces:**
- Consumes: `WindowsSupplyLock`
- Produces: `validate_runtime_archive(path: Path, supply: SupplyArtifact) -> tuple[ZipInfo, ...]`、
  `safe_zip_members(archive: ZipFile) -> tuple[ZipInfo, ...]`、
  `validate_webview2_installer(path: Path, supply: SupplyArtifact, license_evidence: Path) -> None`、
  `stage_windows_supplies(lock: WindowsSupplyLock, cache_dir: Path, output_dir: Path) -> dict[str, str]`

`scripts/test_stage_windows_runtime.py`は`TemporaryDirectory`内へsynthetic ZIPを作る
次のhelperを定義する。

```python
@contextmanager
def zip_fixture(entries: Mapping[str, bytes]) -> Iterator[ZipFile]:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.zip"
        with ZipFile(path, "w") as writer:
            for name, body in entries.items():
                writer.writestr(name, body)
        with ZipFile(path) as reader:
            yield reader
```

- [ ] **Step 1: archive攻撃fixtureの失敗testを書く**

```python
def test_rejects_parent_traversal() -> None:
    with zip_fixture({"../escape.py": b"x"}) as archive:
        with assert_raises_code("unsafe_archive_member"):
            safe_zip_members(archive)


def test_rejects_absolute_and_device_paths() -> None:
    for name in (r"C:\escape.exe", r"\\.\device", "/absolute"):
        with zip_fixture({name: b"x"}) as archive:
            with assert_raises_code("unsafe_archive_member"):
                safe_zip_members(archive)
```

Python ZIPの欠落、size / SHA不一致、unsafe link、reparse point、license欠落、
展開対象`python.exe`の非x64 PE、Python version不一致を
`validate_runtime_archive()`経由で検査する。

```python
def test_runtime_archive_missing_is_rejected() -> None:
    with TemporaryDirectory() as directory:
        missing = Path(directory) / "python-runtime.zip"
        with assert_raises_code("missing_runtime_archive"):
            validate_runtime_archive(missing, python_supply_fixture())


def test_runtime_archive_corrupt_sha_is_rejected() -> None:
    with runtime_zip_fixture(machine=0x8664, extra=b"corrupt") as archive:
        with assert_raises_code("supply_sha_mismatch"):
            validate_runtime_archive(archive, python_supply_fixture())


def test_runtime_archive_wrong_architecture_is_rejected() -> None:
    with runtime_zip_fixture(machine=0x014C) as archive:
        supply = supply_for_file(archive, architecture="x64")
        with assert_raises_code("unsupported_architecture"):
            validate_runtime_archive(archive, supply)
```

WebView2 `.exe`はZIP fixtureへ渡さず、production functionを直接検査する。

```python
def test_webview2_missing_is_rejected() -> None:
    missing = Path("fixture-missing-webview2.exe")
    with assert_raises_code("missing_webview2_installer"):
        validate_webview2_installer(
            missing,
            webview2_supply_fixture(),
            webview2_license_fixture(),
        )


def test_webview2_corrupt_sha_is_rejected() -> None:
    with pe_file_fixture(machine=0x8664, body=b"corrupt") as installer:
        with assert_raises_code("supply_sha_mismatch"):
            validate_webview2_installer(
                installer,
                webview2_supply_fixture(),
                webview2_license_fixture(),
            )


def test_webview2_wrong_architecture_is_rejected() -> None:
    with pe_file_fixture(machine=0x014C) as installer:
        supply = supply_for_file(installer, architecture="x64")
        with assert_raises_code("unsupported_architecture"):
            validate_webview2_installer(
                installer,
                supply,
                webview2_license_fixture(),
            )
```

`pe_file_fixture`はsynthetic DOS header、PE signature、machine fieldを持つfileを
`TemporaryDirectory`内へ作る。Python runtime側もmissing archive、corrupt SHA、
embedded `python.exe`のmachine `0x014C`を`validate_runtime_archive()`へ渡して
それぞれ`missing_runtime_archive`、`supply_sha_mismatch`、
`unsupported_architecture`を確認する。

- [ ] **Step 2: REDを確認する**

Run:

```bash
python3 scripts/test_stage_windows_runtime.py
```

Expected: `stage-windows-runtime.py`未作成でFAIL。

- [ ] **Step 3: 標準ライブラリで最小stagerを実装する**

- Python runtimeは`hashlib`でZIPのsize / SHA / artifact名を検査し、
  `zipfile`の全memberを検査後にだけ展開する。
- Python ZIP内と展開後のlicense SHA、`python.exe`のPE machine `0x8664`を確認する。
- WebView2 `.exe`は展開しない。artifact名、size、SHA、PE machine `0x8664`、
  別fileのlicense evidence SHAを`validate_webview2_installer()`で確認する。
- Pythonは`build/windows-runtime/python/`、WebView2は
  `build/windows-runtime/webview2/`の専用一時directoryへstageする。
- WebView2は検査済みbytesを専用stage先へcopyし、copy後SHAを再検査してrenameする。
- PythonまたはWebView2が不足してもPATH / networkへfallbackしない。

- [ ] **Step 4: GREENを確認する**

Run:

```bash
python3 scripts/test_stage_windows_runtime.py
python3 -m py_compile scripts/stage-windows-runtime.py
```

Expected: Python ZIPとopaque WebView2 `.exe`のproduction検証testがpass。

- [ ] **Step 5: runtime / WebView2取得の個別承認で停止する**

Directorはlockのartifact名、URL、size、SHA、license、書込先、必要容量を示す。
外部download、cache作成、展開はそれぞれ承認後だけ実行する。download bytesがlockと
一致しなければ削除せず`dist/rejected/windows/supply/`へ隔離し、実行権限を付与せず、
candidate glob / CI upload / signing inputから除外する。隔離記録へreason、size、SHA、
記録時刻、30日期限を残すが自動削除しない。削除は別承認を得る。

- [ ] **Step 6: 承認済みcacheだけでstageする**

Run:

```bash
python3 scripts/stage-windows-runtime.py \
  --lock docs/windows-release/windows-supply-lock.json \
  --cache build/windows-cache \
  --output build/windows-runtime
```

Expected: `windows supplies staged`、manifestにPython / WebView2 SHAとlicense SHA。

- [ ] **Step 7: commit stop**

build outputをstageせず、scriptとtestだけを明示的に`git add`する。承認がある場合だけ
`git commit -m "feat: stage verified Windows runtimes"`を実行する。

---

### Task 4: 既存migrationのWindows characterization / no-op Gate

**Files:**
- Modify: `scripts/test_migration_manager.py`
- Read-only: `migration_manager.py`
- Read: `MEMORY.md`
- Read: `app_paths.py`

**Interfaces:**
- Consumes: `windows_data_root()`、legacy allowlist、
  `detect_legacy_sources(known_roots, paths) -> list[MigrationSource]`、
  `build_migration_preview(sources) -> dict`、
  `apply_migration(preview_id, approved_items, paths) -> dict`、
  `rollback_migration(snapshot_id, paths) -> dict`
- Produces: Windows `TomosPaths` fixtureによる既存generic migrationの合格証跡

本Taskは新しいWindows migration interfaceを作らない。既存generic migrationが
Windows fixtureで合格するかをcharacterizationし、合格時はproduction no-opとする。

Legacy allowlist:

```text
%USERPROFILE%\Library\Application Support\com.shibapapastudio.tomos-ai
%USERPROFILE%\.gemma4-data
```

- [ ] **Step 1: Windows characterization testだけを書く**

`scripts/test_migration_manager.py`へ、`TomosPaths.from_root()`を使うWindows fixtureと
次のproduction呼出しを追加する。

```text
detect_legacy_sources(...)
  → build_migration_preview(sources)
  → apply_migration(preview["previewId"], approved_kinds, paths)
  → rollback_migration(result["snapshotId"], paths)
```

空 / 不一致`approved_kinds`の既存`MigrationApprovalError`、既存
`preview["items"][index]["conflict"]`、applyの`status == "completed"`、
rollbackの`status == "rolled_back"`、元データ非削除、stale preview拒否を検査する。
新dataclass、helperと同名のproduction function、新例外classは追加しない。

- [ ] **Step 2: characterizationを実行してGREEN / REDを分岐する**

Run:

```bash
python3 scripts/test_migration_manager.py
```

Expected: 既存generic migrationのままWindows fixtureを含む全testがGREEN。

- [ ] **Step 3: GREENならproduction no-opを確定する**

GREENの場合、`migration_manager.py`を変更しない。preview hash、承認照合、stale拒否、
snapshot、rollback、競合、自動merge禁止、source非削除は既存実装を再利用し、
同等機能を再実装しない。差分がtest fileだけであることを確認する。

- [ ] **Step 4: REDならこのplan内で実装せず停止する**

実行時に実際の不足が観測された場合は、失敗command、exit、fixture、期待値、
不足したproduction interfaceをDirectorへ返す。観測した不足だけを対象にした別RED testと
最小変更の再計画を作り、別reviewと承認を得る。このplanで推測して
`migration_manager.py`を変更しない。

- [ ] **Step 5: 実データ操作の承認で停止する**

characterizationはtemp fixtureだけで行う。実ユーザーデータの検出、copy、rollbackは
D2の実機planで対象、件数、容量、rollbackを示して承認後だけ実行する。

- [ ] **Step 6: test-only commit stop**

```bash
git diff --check
git diff --name-only
python3 scripts/test_migration_manager.py
```

Expected: GREEN、Task 4差分は`scripts/test_migration_manager.py`だけ。
明示承認がある場合だけ
`git commit -m "test: characterize Windows data migration"`を実行する。

---

### Task 5: Tauri x64 MSI bundle契約を実装する

**Files:**
- Modify: `src-tauri/tauri.conf.json`
- Modify: `src-tauri/Cargo.toml`
- Modify: `src-tauri/Cargo.lock`
- Modify: `scripts/make-windows-msi.py`
- Create: `scripts/test_windows_msi_bundle.py`
- Test: `scripts/test-desktop-release-version.py`
- Test: `scripts/test-pwa-assets.js`

**Interfaces:**
- Consumes: ProductCode、UpgradeCode、`build/windows-runtime`、M0 source manifest
- Produces: `build_windows_msi_plan(lock_path: Path, source_manifest: Path) -> WindowsMsiPlan`、unsigned MSI build command、resource allowlist

```python
@dataclass(frozen=True)
class WindowsMsiPlan:
    version: str
    architecture: str
    product_code: str
    upgrade_code: str
    bundle_targets: tuple[str, ...]
    python_source: str
    allow_path_fallback: bool
    python_artifact_name: str
    python_size: int
    python_sha256: str
    python_license_sha256: str
    webview2_artifact_name: str
    webview2_size: int
    webview2_sha256: str
    webview2_license_sha256: str
    resource_paths: tuple[str, ...]
    source_commit: str
    source_tree_sha: str
```

M0 handoff manifestは`docs/releases/windows-source-manifest.json`へ固定し、次をmappingする。

```text
release_version -> WindowsMsiPlan.version
tag_target_commit -> WindowsMsiPlan.source_commit
source_tree_sha -> WindowsMsiPlan.source_tree_sha
source_clean -> build許可（trueだけ）
python_runtime / webview2 supply lock -> artifact名、size、SHA、license SHA
```

- [ ] **Step 1: M0 handoffとdependency変更の承認を先に得る**

M0 Task 8のcommit、tree、manifest SHA、clean状態、shared file一覧をreadbackする。
Directorが4 shared fileのowner移管を明示するまで編集しない。Tauri / Cargo / WiXの
dependencyまたはCargo.lock変更が必要な場合は、package、version、license、対象fileを
示して承認を得る。承認前にdependency、Cargo.lock、WiX設定を変更しない。

- [ ] **Step 2: MSI contractの失敗testを書く**

```python
def test_bundle_is_x64_msi() -> None:
    plan = build_windows_msi_plan(
        lock_path=windows_supply_lock_fixture(),
        source_manifest=windows_source_manifest_fixture(),
    )
    assert plan.architecture == "x64"
    assert plan.bundle_targets == ("msi",)


def test_release_bundle_never_uses_path_python() -> None:
    plan = build_windows_msi_plan(
        lock_path=windows_supply_lock_fixture(),
        source_manifest=windows_source_manifest_fixture(),
    )
    assert plan.python_source == "bundled"
    assert plan.allow_path_fallback is False


def test_bundle_preserves_locked_supply_fields() -> None:
    plan = build_windows_msi_plan(
        lock_path=windows_supply_lock_fixture(),
        source_manifest=windows_source_manifest_fixture(),
    )
    assert plan.python_sha256 == "B" * 64
    assert plan.python_license_sha256 == "D" * 64
    assert plan.webview2_sha256 == "C" * 64
    assert plan.webview2_license_sha256 == "D" * 64


def test_wix_uses_fixed_install_root() -> None:
    plan = build_windows_msi_plan(
        lock_path=windows_supply_lock_fixture(),
        source_manifest=windows_source_manifest_fixture(),
    )
    wix = render_wix_source(plan)
    require_tokens_in_order(
        wix,
        ("ProgramFilesFolder", "ShibaPapa Studio", "TOMOS AI"),
    )
```

UpgradeCode、ProductCode、version、runtime / WebView2 SHA、resource allowlist、
user data非同梱、WebView2 corrupt errorをproduction `build_windows_msi_plan()`と
`render_wix_source()`へfixture fileを渡して検査する。source manifest / supply lockの
片側SHAを変えたfixtureは`source_lock_mismatch`でFAILさせる。

- [ ] **Step 3: REDを確認する**

Run:

```bash
python3 scripts/test_windows_msi_bundle.py
```

Expected: Windows MSI plan interface未定義でFAIL。

- [ ] **Step 4: 最小bundle planを実装する**

`make-windows-msi.py`はlockとM0 source manifestを読み、version / commit / tree /
runtime SHAが一致しない場合にbuild commandを返さない。resourceは検証済み
`build/windows-runtime`だけをallowlistし、secretsとuser data pathを含めない。
WiX production generatorは`ProgramFilesFolder`配下に`ShibaPapa Studio`、
その配下に`TOMOS AI`を生成する。app runtimeはTask 2で更新した
`tomos_data_root()`を使い、MSI install rootとuser data rootを混同しない。

- [ ] **Step 5: GREENと回帰を確認する**

Run:

```bash
python3 scripts/test_windows_msi_bundle.py
python3 scripts/test-desktop-release-version.py
node scripts/test-pwa-assets.js
python3 -m py_compile scripts/make-windows-msi.py
cargo test --manifest-path src-tauri/Cargo.toml
git diff --check
```

Expected: static / unit contract pass。MSI artifactはまだ生成しない。

- [ ] **Step 6: MSI buildの個別承認で停止する**

unsigned MSI buildは入力commit、tree、runtime SHA、出力先、必要容量を示して
dependency承認とは別の承認を得る。

- [ ] **Step 7: 承認後だけunsigned MSIをbuildする**

Run:

```bash
python3 scripts/make-windows-msi.py \
  --lock docs/windows-release/windows-supply-lock.json \
  --source-manifest docs/releases/windows-source-manifest.json \
  --output dist/windows-unsigned
```

Expected: unsigned MSI、build evidence、SHA。公開候補directoryへ移さない。

- [ ] **Step 8: production pathを静的readbackしてcommit stop**

生成WiX sourceが`ProgramFilesFolder\ShibaPapa Studio\TOMOS AI`を持ち、
production `tomos_data_root()`がWindows fixtureで
`%LOCALAPPDATA%\ShibaPapa Studio\TOMOS AI`へ解決されるtest結果をD1 evidenceへ保存する。
どちらかがfixture helperだけを検査していた場合はD2へ進めない。

artifactとbuild outputをstageしない。明示承認がある場合だけ
`git commit -m "feat: package TOMOS Windows MSI"`を実行する。

---

### Task 6: unsigned CIと署名secret境界を実装する

**Files:**
- Create: `.github/workflows/windows-signed-msi.yml`
- Create: `scripts/verify-windows-signature.ps1`
- Create: `scripts/windows_signed_candidate.py`
- Create: `scripts/test_windows_signing_contract.py`
- Create after approved signing: `docs/windows-release/signed-candidate-evidence.json`
- Create after approved Environment readback: `docs/windows-release/environment-reviewer-evidence.md`
- Read-only: `scripts/release_manifest.py`
- Read-only: `scripts/test_release_manifest.py`

**Interfaces:**
- Consumes: unsigned MSI、certificate lock、timestamp lock、M0 source manifest
- Produces: unsigned test job、no-secret preflight job、protected signing job、
  `verify_windows_signature(path, expected_subject, expected_timestamp) -> SignatureEvidence`、
  `signed_candidate_evidence`

```python
@dataclass(frozen=True)
class SignatureEvidence:
    path_name: str
    sha256: str
    subject: str
    issuer: str
    fingerprint: str
    timestamp: str
    timestamp_url: str
    valid: bool
```

- [ ] **Step 1: workflow file作成の承認を先に得る**

Directorはworkflow名、trigger、job、protected Environment、secret名、外部artifact
store、課金有無、変更fileを秘密値なしで示す。承認前に`.github/workflows/`を
変更しない。

- [ ] **Step 2: workflow / signatureの失敗testを書く**

```python
def test_signing_requires_manual_protected_environment() -> None:
    workflow = Path(".github/workflows/windows-signed-msi.yml").read_text()
    require_tokens_in_order(
        workflow,
        (
            "workflow_dispatch:",
            "preflight:",
            "sign:",
            "if: github.event_name == 'workflow_dispatch'",
            "environment: windows-signing",
        ),
    )


def test_push_and_pull_request_cannot_reach_sign_job() -> None:
    workflow = Path(".github/workflows/windows-signed-msi.yml").read_text()
    trigger_block = workflow.split("jobs:", 1)[0]
    assert "\n  push:" in trigger_block
    assert "\n  pull_request:" in trigger_block
    sign_block = workflow.split("\n  sign:", 1)[1]
    assert "github.event_name == 'workflow_dispatch'" in sign_block
```

`require_tokens_in_order(text, tokens)`はtest file内で`str.find`を順に検査し、欠落または
逆順なら`AssertionError`を投げる。YAML parser dependencyは追加しない。

fork / PR secretなし、no-secret preflightとsign job分離、cache / artifact / summary /
logへのsecret禁止、exe / dll → MSI順、wrong signer、missing / invalid timestamp、
SHA変化を検査する。

- [ ] **Step 3: REDを確認する**

Run:

```bash
python3 scripts/test_windows_signing_contract.py
```

Expected: workflow / verifier未作成でFAIL。

- [ ] **Step 4: unsigned jobとno-secret preflightを実装する**

PR / fork /通常pushでTask 1から5のunit / static testを実行する。unsigned artifactには
`UNSIGNED-NOT-FOR-DISTRIBUTION`を付け、Releaseへuploadしない。

`preflight` jobはEnvironmentを付けずsecretを一切参照しない。supply lock、source
manifest、unsigned MSI SHA、署名対象一覧を検証し、固定schemaのpreflight evidenceだけを
job artifactへ渡す。preflight evidenceにrepo script pathや任意commandを含めない。

- [ ] **Step 5: protected signing jobを実装する**

sign jobは`workflow_dispatch`とprotected Environmentを必須にし、検証済みpreflight
jobだけを`needs`にする。開始直後にunsigned MSI SHAを再計算してevidenceと一致させ、
その後は固定PowerShell署名commandとsignature verifierだけを実行する。secret利用開始後に
任意repo script、package install、buildを実行しない。exe / dllを署名・検査し、
MSIを最後に署名・検査する。verifierはsubject、issuer、fingerprint、timestamp、SHAを
JSON evidenceとして返し、secret値を返さない。

- [ ] **Step 6: GREENを確認する**

Run:

```bash
python3 scripts/test_windows_signing_contract.py
python3 scripts/test_release_manifest.py
python3 -m py_compile \
  scripts/test_windows_signing_contract.py \
  scripts/windows_signed_candidate.py
git diff --check
```

Expected: static contract pass。workflowはまだ実行しない。

- [ ] **Step 7: Environment reviewerをreadbackしてsecret登録承認で停止する**

Directorはprovider、課金有無、secret名、protected Environment、required reviewer、
sign対象、timestamp URL、出力先を秘密値なしで示す。GitHub Environmentのrequired
reviewer設定を外部readbackし、reviewer人数、保護branch、readback時刻を
`environment-reviewer-evidence.md`へ保存する。secret登録とworkflow実行は別々に
承認を得る。tag、push、candidate upload、Release公開はこの承認に含めない。

- [ ] **Step 8: 承認後だけsigned candidate evidenceを作る**

署名後bytesからMSI SHAを計算し、署名者 / timestamp evidenceとともに
`docs/windows-release/signed-candidate-evidence.json`へ記録する。fieldはsource
manifest SHA、unsigned SHA、signed MSI SHA、署名者、issuer、fingerprint、timestamp、
timestamp URL、workflow run IDとする。`third_party_tested_sha256`を持たせず、D1で
final manifestと呼ばない。署名不合格物は`dist/rejected/windows/signing/`へ隔離し、
candidate glob / CI uploadから除外する。

- [ ] **Step 9: candidate uploadの別承認で停止する**

署名実行とcandidate uploadを別jobにする。Directorはsigned MSI名、size、SHA、
upload先、保持期間、公開範囲を示し、別承認を得る。未承認時は非公開candidateとして
停止する。tag / Release添付はREL0のさらに別承認とする。

- [ ] **Step 10: commit stop**

workflow、validator、evidence schemaだけをstageし、secret、certificate、artifactを
含めない。
明示承認がある場合だけ`git commit -m "ci: add protected Windows MSI signing"`を
実行する。

---

### Task 7: D1全体検証とD2 handoffを固定する

**Files:**
- Create: `docs/tomos-windows-d1-gate-report-2026-08-01.ja.md`
- Read: `docs/releases/windows-source-manifest.json`
- Read: `docs/windows-release/signed-candidate-evidence.json`
- Test: Task 1から6の全test

**Interfaces:**
- Consumes: supply lock、M0 source manifest、署名済みcandidate、signed candidate evidence
- Produces: D1 Gate報告、`2026-08-01-tomos-windows-real-machine-release.md`の入力

- [ ] **Step 1: clean sourceをreadbackする**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/main
```

Expected: source commit / treeがM0 handoff manifestと一致。dirtyまたはhandoff前なら
D1を合格にしない。

- [ ] **Step 2: 全自動testをfreshに実行する**

Run:

```bash
python3 scripts/test_windows_supply_lock.py
python3 scripts/test_windows_msi_contract.py
python3 scripts/test_app_paths.py
python3 scripts/test_stage_windows_runtime.py
python3 scripts/test_migration_manager.py
python3 scripts/test_windows_msi_bundle.py
python3 scripts/test_windows_signing_contract.py
python3 scripts/test_release_manifest.py
python3 scripts/test-desktop-release-version.py
node scripts/test-pwa-assets.js
cargo test --manifest-path src-tauri/Cargo.toml
git diff --check
```

Expected: 全command exit 0。

- [ ] **Step 3: 署名済みcandidateの現物readbackを行う**

PowerShellでexe / dll / MSIの署名者、issuer、fingerprint、RFC 3161 timestamp、
SHAを再取得しlockと`signed_candidate_evidence`へ照合する。M0 source manifestは
source stageのまま変更しない。D1ではfinal manifestを生成しない。
D2 / D3の第三者試験後、`third_party_tested_sha256 == artifact.sha256`が成立した場合だけ
M0 ownerがfinal manifestを生成する。

- [ ] **Step 4: production install / data pathを静的readbackする**

`render_wix_source(build_windows_msi_plan(...))`の実出力から
`ProgramFilesFolder\ShibaPapa Studio\TOMOS AI`を確認し、production
`tomos_data_root()`のWindows fixture実行から
`%LOCALAPPDATA%\ShibaPapa Studio\TOMOS AI`を確認する。fixture helperだけの値を
evidenceにしない。結果をD1報告へ保存する。

- [ ] **Step 5: D1 Gate報告を書く**

報告見出し:

```text
開始点
Supply lock
Unsigned tests
Signed candidate evidence
M0 source manifest
Production paths
未実行
承認待ち
Gate判定
```

D1ではinstall、uninstall、update、rollback、第三者試験、公開を合格扱いしない。

- [ ] **Step 6: D2 / D3へ引き渡して停止する**

`docs/superpowers/plans/2026-08-01-tomos-windows-real-machine-release.md`はD1合格後に
別計画として作成する。対象MSI SHA、user data snapshot、install / uninstall、
第三者試験を示して個別承認を得る。

- [ ] **Step 7: final commit / push stop**

D1の全Task commitをDirectorがreviewする。ユーザーのcommit承認がある場合だけGate
報告をcommitする。pushは別承認、PRは別承認、mergeはchecks合格後の別判断とする。

---

## Plan Verification Matrix

| Requirement | Task |
| --- | --- |
| certificate / timestampの実在lock | Task 1、6 |
| Python runtime / license / SHA | Task 1、3 |
| WebView2 offline / license / SHA | Task 1、3 |
| deterministic ProductCode / UpgradeCode | Task 2、5 |
| ProgramFiles / LOCALAPPDATA分離 | Task 2 |
| legacy preview / approved copy / rollback | Task 4 |
| PATH Python / network fallback禁止 | Task 3、5 |
| MSI resource / version / source整合 | Task 5 |
| exe / dll → MSI署名順 | Task 6 |
| protected Environment / required reviewer | Task 6 |
| tag自動署名 / 自動公開禁止 | Task 6 |
| D2 / D3実機境界 | Task 7 |

## Program Stop Rules

次の場合はそのTaskを停止し、他の安全なstatic testだけを進める。

- external readback、certificate、runtime、WebView2の実在値が未承認。
- dependency、secret、CI、build、署名、実機変更、commit、pushが未承認。
- supply lockとdownload bytes、source manifest、certificate evidenceが不一致。
- UpgradeCode履歴が`7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1`と一致しない。
- user dataを削除、auto-merge、外部送信する必要が生じる。
- secret、user path、会話、Memory、Knowledgeがlog / artifactへ入る。
- baseline failureと新規failureを分離できない。
- 同じshared fileを別ownerが変更中。

停止時は確認済み、未確認、拒否した入力、必要approvalをD1報告へ分けて記録する。
