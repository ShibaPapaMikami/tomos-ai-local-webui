# TOMOS Windows署名MSI Design

**Gate:** D0

**Owner:** エンジニア2

**Entry:** Gate R0合格

**Status:** 承認用design。未確定の供給元・証明書情報を外部readbackするまでD0合格にしない。

## Goal

Windows x64版を署名済みMSIとして安全に配布するため、署名、runtime、WebView2、
保存先、upgrade、rollback、CI secretの境界を固定する。

## Source of Truth

- `AGENTS.md`
- `DESIGN.md`
- `VOICE.md`
- `MEMORY.md`
- `PLUGIN.md`
- `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`
- `docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md`
- `docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md`
- `docs/superpowers/plans/2026-08-01-tomos-release-traceability.md`
- `docs/superpowers/specs/2026-07-26-tomos-macos-portable-runtime-and-notarized-pkg-design.md`

Mac設計のデータ保全原則は参照するが、path、署名、installer、rollbackはWindows固有値で
再定義する。

## Scope

### Owned files

Task 4では本design文書だけを所有する。

```text
docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md
```

### Read-only references

- `src-tauri/tauri.conf.json`
- 現行WiX設定とstable UpgradeCode
- `scripts/make-windows-msi.py`
- `app_paths.py`、`migration_manager.py`
- M0 release manifest contract

### Produces

- D1署名CI実装の固定契約
- D2実機install / update / uninstall / reinstall契約
- D3第三者試験とrollback契約
- Windows runtime / WebView2外部readbackの承認停止点

## Non-goals

- certificate取得、購入、更新
- secret登録、key upload
- dependency / runtime / WebView2取得
- workflow作成・実行
- MSI build、署名、実機install
- tag、push、Release公開
- user data移行の実行

## Interfaces

### Consumes

- Task 4で承認済みのM0 schema / validator contract
- 既存Tauri appとWiX identity
- Desktop B3のpreview、承認copy、rollback原則

### Produces

- `2026-08-01-tomos-windows-signed-msi.md`のD1入口
- `2026-08-01-tomos-windows-real-machine-release.md`のD2/D3入口
- M0 source-lockがconsumeするWindows certificate、runtime、WebView2、identity供給値
- U2 / D3が使うWindows第三者試験欄とrollback 3区分
- U0FとREL0へ渡す署名済みMSI evidence

## Code-signing and Timestamp

1. bundled exe / dllを先に署名し、MSIを最後に署名する。
2. Authenticode digestはSHA-256を使う。
3. 固定RFC 3161 HTTPS timestampとSHA-256 timestamp digestを使う。
4. publisher subject、issuer、certificate fingerprint / key identity、有効期間を
   D1開始前に固定する。
5. 次で署名者とtimestampをreadbackする。

```powershell
Get-AuthenticodeSignature <path>
signtool verify /pa /all /v <path>
```

6. cloud / HSM signingまたは承認済みself-hosted runnerのどちらを使うか別承認で決める。
7. issuer、subject、timestamp URL、key保管方式を推測しない。
8. timestamp失敗、期限外、署名者不一致の成果物をcandidateへ出さない。

## Python Runtime Supply Contract

Windows x64 Python runtimeについて次をmanifestへ固定する。

```text
official source
release version
artifact name
download URL
archive size
archive SHA-256
license name / URL / included file SHA-256
supported architecture
```

検証:

- download bytesのsize / SHAを展開前に確認する。
- archiveと展開後licenseを確認する。
- `..`、absolute path、device path、unsafe link、reparse pointを拒否する。
- 実行fileがx64であることとPython versionを確認する。
- release buildはPATH上のPythonへfallbackしない。
- source、license、SHAの正確な外部readback前はD0を合格にしない。

## WebView2 Contract

1. 公式x64 offline installerの固定同梱を第一候補とする。
2. source、version、再配布license、size、SHA-256をmanifestへ記録する。
3. absent / corrupt時は日本語の固定error codeで停止する。
4. WebView2失敗時にuser dataを変更しない。
5. bootstrapperの無断downloadを採用しない。
6. 正確な再配布条件とSHAの外部readback前はD0を合格にしない。

## Install and Data Paths

Install:

```text
%ProgramFiles%\ShibaPapa Studio\TOMOS AI
```

User data:

```text
%LOCALAPPDATA%\ShibaPapa Studio\TOMOS AI
```

固定条件:

- install payloadとuser dataを分離する。
- uninstallでMemory、Knowledge、教材、設定、chat、modelを削除しない。
- `LOCALAPPDATA`がmissing、relative、install root内、reparse escapeならfail closed。
- user名やfull pathをdiagnostics、manifest、CI logへ出さない。

## Legacy Copy Contract

検出allowlist:

```text
%USERPROFILE%\Library\Application Support\com.shibapapastudio.tomos-ai
%USERPROFILE%\.gemma4-data
```

順序:

```text
read-only検出
  → 件数・容量・競合preview
  → ユーザー承認
  → staging copy
  → 件数・hash検証
  → publish
```

- 元データを削除しない。
- 新旧に同kindがある場合は自動mergeしない。
- Memoryコピーは内容を表示せず明示承認を必須にする。
- rollback用にコピー前状態とtransfer manifestを保持する。
- path allowlist外、symlink / reparse escapeは拒否する。

## Upgrade Identity

Stable UpgradeCode:

```text
7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1
```

ProductCode:

- version / architecture別に決定する。
- 同版再buildは同じProductCode、別版は別ProductCode。
- UUIDv5 namespaceを
  `C3C54504-8F05-5B59-AB5E-14E70A734EB8`へ固定する。
- UUIDv5の正規化入力は
  `TOMOS AI|<architecture>|<version>`へ固定する。
- product名はASCIIの`TOMOS AI`、architectureは小文字の`x64`、versionは先頭`v`なし、
  前後空白なしのSemVer（例: `0.8.234`）に正規化する。
- MSIへ渡すProductCodeはUUIDv5結果を大文字・波括弧付き表記にする。
- 同じversion / architectureは同じProductCode、異なるversionまたはarchitectureは
  異なるProductCodeになることを静的testで固定する。
- 過去MSIのUpgradeCodeが異なる場合は実装を停止する。

Version、ProductCode、UpgradeCode、source commit、tree、artifact SHAはM0 manifestで
一意に追跡する。

## Rollback Contract

### 初回署名Windows版

- 旧署名版へのapp rollbackを表示しない。
- 同版再導入を実証する。
- data snapshot復元と設定copy rollbackを別々に実証する。
- uninstall / reinstallでuser dataを保持する。

### 次版以降

- schema互換を確認した直前の署名済みMSIだけをapp rollback対象にする。
- rollback前に現在dataを別snapshotとして保全する。
- schema非互換版へ直接戻さない。
- app、data、設定の3種類を試験票で分ける。

自動削除を行わない。snapshot削除は対象、容量、復旧不能範囲を示して別承認を得る。

## CI Secret Boundary

- PR、fork、通常pushはunsigned build / testだけ。
- signingは`workflow_dispatch`、protected Environment、required reviewerを必須にする。
- tag pushだけで自動署名しない。
- secretをfork、cache、artifact、summary、logへ出さない。
- version、commit、tree、runtime SHA一致後だけsigning jobへ進む。
- exe / dll署名後に検査し、最後にMSIを署名する。
- 署名者、timestamp、SHA合格後だけcandidateをuploadする。
- candidate uploadとtag / Release公開を別approvalにする。

## TDD and Verification Plan

D1 planでは次を失敗testから固定する。

1. runtime / WebView2 manifestのexact schema。
2. archive traversal、absolute path、unsafe link、reparse point拒否。
3. PATH Python fallback禁止。
4. stable UpgradeCodeとdeterministic ProductCode。
   namespace、正規化入力、大小文字、波括弧表記も固定する。
5. LOCALAPPDATA path fail-closed。
6. uninstall時のuser data保持。
7. legacy preview、承認、staging、hash、publish、rollback。
8. unsigned / invalid timestamp / wrong signerのcandidate拒否。
9. secretがlog、artifact、cacheへ出ないworkflow契約。
10. 初回版と次版以降のrollback表示差。

回帰候補:

```text
python3 scripts/test_release_manifest.py
python3 scripts/test-desktop-release-version.py
python3 scripts/test_macos_tomos_resources.py
python3 scripts/test-desktop-shell-contract.py
cargo test --manifest-path src-tauri/Cargo.toml
git diff --check
```

外部取得、build、署名、実機testは静的testと分ける。

## Approval Stops

- 本designのDirector reviewとユーザー承認前はD0実装を開始しない。
- certificate provider、timestamp、key保管方式の選定は別承認。
- Python runtime / WebView2の外部readbackと取得は操作内容を示して別承認。
- 課金service、dependency、secret登録は個別承認。
- workflow実行、MSI build、署名、実機installは個別承認。
- tag、push、Release公開はREL0で別承認。
- commitは明示承認まで行わない。

## Acceptance Criteria

- certificate subject / issuer / fingerprint、timestamp、key保管方式が固定。
- Python runtimeのsource、license、size、SHAが固定。
- WebView2のsource、license、size、SHAが固定。
- install / data pathとfail-closed条件が固定。
- UpgradeCode / ProductCode規則が固定。
- 同一version / architectureから同じProductCodeを再生成できる。
- 初回版と次版以降のrollback差が固定。
- CI secret境界と署名順序が固定。
- M0 manifestでversionからartifactまで追跡できる。
- 未承認取得、secret、workflow、build、署名、実機変更を行っていない。

一つでも未確定ならGate D0は`検証中`とする。

## Handoff

| Plan | Entry | Approval stop |
| --- | --- | --- |
| `2026-08-01-tomos-windows-signed-msi.md` | D0設計承認 | 依存、runtime取得、署名secret CI |
| `2026-08-01-tomos-windows-real-machine-release.md` | D1合格 | install、uninstall、第三者試験 |
| `2026-08-01-tomos-v0.8.234-release-publication.md` | Final Mac M2、D3、U0F合格 | tag、push、Release公開 |

Windows D3後は最終release commitからMac M1/M2を再実行し、最終PKG/MSI SHAで
第三者smokeを行う。再buildしたplatformはsmokeをやり直す。

## Open Decisions

- certificate provider、publisher subject、issuer、fingerprint / key identity。
- RFC 3161 timestamp URL。
- cloud/HSM signingまたはself-hosted runner。
- Windows x64 Python runtimeの正確なartifact、license、size、SHA。
- WebView2 offline installerのversion、license、size、SHA。
- 過去Windows MSIのUpgradeCode readback。

これらを推測で埋めず、承認済み外部readbackと現物証跡で確定する。

## Stop Rules

- certificate、timestamp、runtime、WebView2、UpgradeCode履歴が未確認。
- 課金、外部service、dependency、secretが未承認。
- shared file競合、実装、外部取得、workflow、実機操作が必要。
- Memory、Knowledge、chat、secret、full pathがartifact / logへ入る。
- baseline failureと新規failureを分離できない。

停止時はD0を合格にせず、未確定項目と必要承認をDirectorへ返す。
