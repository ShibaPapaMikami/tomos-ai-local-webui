# TOMOS Release追跡契約 Implementation Plan

**Gate:** M0

**Owner:** エンジニア2

**Entry:** Gate R0合格

**Goal:** 正式候補`0.8.234`のversion、tag対象commit、tree、runtime、artifactを
一意に追跡できるmanifest契約と標準ライブラリvalidatorを作る。

**Architecture:** 先にschema / validator contractを承認可能な形で固定し、D0が
同schemaでWindows supply値を確定した後、M0が実在source-lockを作る三段階とする。
source確定前の`source` stageと署名後artifactの`final` stageを分離し、tracked
sourceへ自身のcommitを埋め込まず、CI/evidenceが外側からcommit、tree、artifact
SHAを記録する。

## Source of Truth

- `AGENTS.md`
- `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`
- `docs/superpowers/specs/2026-08-01-tomos-post-gate-c-program-design.md`
- `docs/tomos-post-gate-c-r0-gate-report-2026-08-01.ja.md`
- `docs/superpowers/plans/2026-08-01-tomos-post-gate-c-program.md`
- `docs/superpowers/plans/2026-08-01-tomos-beginner-install-docs.md`
- `docs/superpowers/specs/2026-08-01-tomos-windows-signed-msi-design.md`
- `docs/superpowers/specs/2026-07-26-tomos-macos-portable-runtime-and-notarized-pkg-design.md`
- `docs/superpowers/plans/2026-07-26-tomos-desktop-c-macos-signing-pkg.md`

## Scope

### Owned files

```text
server.py
Gemma4_12B_Web.command
Gemma4_12B_全部起動.command
Gemma4_12B_Web.bat
Gemma4_12B_All_Start.bat
src-tauri/Cargo.toml
src-tauri/Cargo.lock
src-tauri/tauri.conf.json
scripts/test-desktop-release-version.py
scripts/test-pwa-assets.js
scripts/test-agent-reach-routing-smoke.py
scripts/release_manifest.py
scripts/test_release_manifest.py
scripts/make-macos-tauri-pkg.sh
scripts/release-gate-macos-tauri.sh
scripts/make-windows-msi.py
scripts/test_macos_tauri_bundle.py
scripts/test_macos_tomos_resources.py
scripts/test_mac_pkg_signing.py
scripts/test_audit_macos_tauri_release.py
scripts/test_sign_macos_tauri_app.py
docs/releases/
```

### Read-only references

- U0文書とU0Fのartifact反映境界
- D0のWindows runtime、WebView2、署名契約
- Gate Cのhistorical v0.8.233証跡
- Gitのcommit / tree / clean状態

### Prohibited changes

- Mac build、署名、公証、install
- Windows runtime取得、WebView2取得、MSI署名
- workflow実行、tag、push、Release公開
- U0、U1、U2、Skill、Voice、Memory、Plugin、Model
- 未生成artifact SHAの記載

## Interfaces

### Consumes

- Gate R0で固定したrelease manifest必須項目
- D0が同schemaで確定するWindows supply値
- schema確定後のclean source commitとtree
- 後続build / signing / third-party testのevidence

### Produces

- `scripts/release_manifest.py`
- `scripts/test_release_manifest.py`
- source / final stageのschemaとfixture
- Mac / Windows manifest一式を検証する`validate_release_set` interface
- source version `0.8.234`の一括整合
- M1/M2、D1/D2/D3、U0F、REL0が使う追跡契約

## Manifest Contract

必須field:

```text
schema_version
stage
release_version
platform
tag_name
tag_target_commit
source_tree_sha
source_clean
ci_run
toolchain
runtime.source
runtime.version
runtime.size
runtime.sha256
runtime.license
artifact.name
artifact.platform
artifact.size
artifact.sha256
signing.subject
signing.timestamp
mac_notary_submission_id
third_party_tested_sha256
```

`source` stageでは未生成artifact、署名、公証、第三者試験fieldを明示的な`null`にする。
`final` stageでは該当platformの必須値をすべて実在値にする。

### Three-stage ordering

1. **M0 Contract:** generic fixtureだけでschema、validator、
   `validate_release_set(mac_manifest, windows_manifest)`を固定する。実在runtime値や
   source-lockを要求しない。
2. **D0 Supply:** D0が承認済みschema contractをconsumeし、Windows certificate、
   runtime、WebView2、installer identityの実在供給値をproduceする。
3. **M0 Source-lock:** D0承認済みsupply値をconsumeし、`0.8.234`のversion、
   tag対象commit、tree、clean状態、platform別source manifestを確定する。

M0 GateはStage 3まで合格して初めて`合格`とする。Stage 1完了をM0 Gate合格と呼ばない。
Stage 1とStage 3は同じ計画内の別review単位とし、D0 supply未確定時に架空値を置かない。

Validatorは次をfail closedにする。

- JSON duplicate key、unknown field、欠落field
- 不正型、40桁commit/tree、64桁SHA、非正size
- absolute path、親directory、symlink
- platformと拡張子の不一致
- artifact SHAと第三者試験SHAの不一致
- source / final stageに許されない値
- historical artifactをcurrent sourceとして扱う入力

`validate_release_set(mac_manifest, windows_manifest)`は次をfail closedにする。

- release version、tag、tag対象commit、source treeの不一致
- platform重複、MacまたはWindowsの欠落
- Macが`.pkg`、Windowsが`.msi`でない組合せ
- 各manifestのthird-party tested SHAとartifact SHAの不一致
- 片側だけcommitまたはtreeを変えた組合せ

## Fixed Decisions

1. 次の正式候補版は`0.8.234`。
2. 現v0.8.233 PKGを現在の`origin/main`由来として再利用しない。
3. ValidatorはPython標準ライブラリだけを使う。
4. final SHAは署名完了後のbytesから計算する。
5. tracked manifestへ自身のcommit SHAを書かない。
6. source commitを先に固定し、evidenceがcommit / tree / artifactを記録する。
7. current source、generic fixture、historical artifactを別directory・別stageにする。
8. U0へartifact実値を書かずU0Fへ渡す。

## Approval Stops

- M0専用worktree作成とsource version変更はDirector開始指示後だけ行う。
- `0.8.234`が別commit / tagに存在した場合は停止する。
- build、依存、署名、公証、artifact、外部取得、公開は個別承認まで行わない。
- source commit / tree / evidence commitの意味が曖昧なら実装を止める。
- commit、pushはそれぞれ明示承認を得る。

## Tasks

### Task 1: clean sourceとversion基準線を固定する

- [ ] 更新済み`origin/main`からM0専用worktreeを作る。
- [ ] HEAD、tree、clean、既存tagをreadbackする。
- [ ] current version `0.8.233`の全出現をOwned files内で記録する。
- [ ] historical artifactとcurrent sourceを分離する。
- [ ] U0 / D0とshared fileが競合していないことを確認する。

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git tag --list 'v0.8.234*'
python3 scripts/test-desktop-release-version.py
```

Expected: clean、競合tagなし、既存version test合格。

### Task 2: 失敗するmanifest testを書く

**Create:** `scripts/test_release_manifest.py`

- [ ] source / finalのvalid fixtureを定義する。
- [ ] duplicate key、unknown field、型、SHA、sizeを拒否する。
- [ ] path traversal、absolute path、symlinkを拒否する。
- [ ] stage別null / required契約を固定する。
- [ ] tag commit、tree、artifact SHAの相関を固定する。
- [ ] historical v0.8.233をcurrent sourceへ流用するfixtureを拒否する。
- [ ] standard library以外のimportを拒否する。
- [ ] `validate_release_set`がversion、tag、commit、tree完全一致を要求する。
- [ ] platform重複、PKG欠落、MSI欠落を拒否する。
- [ ] third-party tested SHAとartifact SHAの不一致を拒否する。
- [ ] Mac / Windows片側だけcommitまたはtreeが異なるfixtureを必ずFAILさせる。

Run:

```bash
python3 scripts/test_release_manifest.py
```

Expected: `scripts/release_manifest.py`未作成でFAIL。

### Task 3: 最小validatorを実装する

**Create:** `scripts/release_manifest.py`

- [ ] `json.loads`へduplicate key検出hookを付ける。
- [ ] exact key setと型を検査する。
- [ ] SHA、commit、tree、size、pathを検査する。
- [ ] source / final stageの条件分岐を実装する。
- [ ] `validate_release_set(mac_manifest, windows_manifest)`を公開interfaceとして
  実装し、単体manifest検査後にrelease-set相関を検査する。
- [ ] 検査結果は秘密情報やuser pathを出さず固定error codeで返す。
- [ ] filesystem検査は明示されたartifact root内だけに限定する。

Run:

```bash
python3 scripts/test_release_manifest.py
python3 -m py_compile scripts/release_manifest.py scripts/test_release_manifest.py
```

Expected: 全manifest unit test合格。

### Task 4: D0へschema contractを引き渡して停止する

- [ ] schema、validator、generic fixtureだけの差分をDirector reviewへ渡す。
- [ ] D0がconsumeするschema versionと必須fieldを固定する。
- [ ] D0のWindows supply値が承認されるまで実在source-lockへ進まない。
- [ ] この時点をM0 Gate合格と記録しない。

### Task 5: D0 supply後にsource versionを0.8.234へ一括整合する

- [ ] versionを使用するOwned filesだけを変更する。
- [ ] Cargo.lockはCargo.tomlと同じversionへ整合する。
- [ ] PWA資産versionとdesktop versionの既存契約を維持する。
- [ ] Mac script/testのhistorical v0.8.233 fixtureは意味を確認し、current sourceだけ更新する。
- [ ] Agent-Reach fallback routingを変更しない。

Run:

```bash
python3 scripts/test-desktop-release-version.py
node scripts/test-pwa-assets.js
python3 scripts/test-agent-reach-routing-smoke.py
```

Expected: `0.8.234`で全version契約合格。

### Task 6: source manifestと後続evidence境界を固定する

**Create:** `docs/releases/`内のschema説明、fixture、運用手順

- [ ] source stageへclean commit / tree / toolchain / runtime契約を記録する。
- [ ] artifact未生成fieldは`null`とする。
- [ ] final evidenceをtracked sourceへself-referenceさせない。
- [ ] 署名後bytes、notary ID、第三者試験SHAの入力時点を説明する。
- [ ] Mac / Windowsが同じtag、version、sourceを使うREL0条件を説明する。
- [ ] 秘密情報、user data、Memory、Knowledge、chat、full pathを禁止する。

### Task 7: release回帰を合格させる

Run:

```bash
python3 scripts/test_release_manifest.py
python3 scripts/test-desktop-release-version.py
node scripts/test-pwa-assets.js
python3 scripts/test-agent-reach-routing-smoke.py
python3 scripts/test_macos_tomos_resources.py
python3 scripts/test_macos_tauri_bundle.py
python3 scripts/test_audit_macos_tauri_release.py
python3 scripts/test_sign_macos_tauri_app.py
python3 scripts/test_mac_pkg_signing.py
python3 -m py_compile scripts/release_manifest.py scripts/test_release_manifest.py
git diff --check
git status --short --branch
```

Artifact引数が必要なtestでは新規artifactを作らず、artifactなしの静的contract modeを
使う。外部取得、署名、公証を開始しない。

### Task 8: Gate M0を判定する

- [ ] version、tag、source commit、tree、artifact SHAの関係が一意。
- [ ] source/final stageが混同されない。
- [ ] D0 supply値を含むsource-lockが確定している。
- [ ] Mac / Windows release-setのversion、tag、commit、tree、platform、SHA相関が合格。
- [ ] historical v0.8.233がcurrent sourceから分離。
- [ ] 全test合格、差分はOwned filesだけ。
- [ ] build、署名、公証、install、公開を行っていない。
- [ ] Director reviewとcommit承認を得る。

## Verification

上記Task 7をfreshに再実行し、実出力、exit code、HEAD、tree、statusをM0報告へ保存する。
未生成artifact fieldが`null`であり、架空SHAが存在しないことをreadbackする。

## Handoff

- `2026-08-01-tomos-macos-v0.8.234-release.md`
  - Entry: M0合格
  - Stop: Developer ID、公証、install、第三者試験
- `2026-08-01-tomos-windows-signed-msi.md`
  - Entry: D0設計承認
  - Stop: 依存、runtime取得、署名secret CI
- U0Fへ最終artifact名、URL、SHAを渡すのはM2 / D3後。
- `2026-08-01-tomos-v0.8.234-release-publication.md`は
  Final Mac M2、D3、U0F合格後だけ開始する。
- Windows D3後の最終release commitからMac M1/M2を再実行する。

## Stop Rules

- `v0.8.234`が別commitに存在。
- shared fileを別ownerが変更中。
- source / tree / evidence commitが曖昧。
- historical artifactとcurrent sourceを分離できない。
- 未生成artifact SHA、dependency、build、署名、公証、外部取得、公開が必要。
- baseline failureと変更起因failureを分離できない。

停止時は版を部分更新せず、作業treeを保持してDirectorへ返す。
