# TOMOS Gate R0 検証報告

**実行日:** 2026-08-01

**判定:** 合格

## 開始点

- branch: `codex/post-gate-c-r0`
- worktree:
  `/Users/masafumimikami/Documents/desktop/Gemma4_12B/.worktrees/post-gate-c-r0`
- HEAD: `374c80186973c568ae3486bb15a9652a8a354b20`
- HEAD tree: `7d2eabfdb05a60b427365bc3b74a4e52c5b8bfd1`
- origin/main: `374c80186973c568ae3486bb15a9652a8a354b20`
- HEADとorigin/main: 一致
- baseline開始時: 追跡対象の変更なし

開始時の実出力:

```text
## codex/post-gate-c-r0...origin/main
374c80186973c568ae3486bb15a9652a8a354b20
7d2eabfdb05a60b427365bc3b74a4e52c5b8bfd1
374c80186973c568ae3486bb15a9652a8a354b20
```

## Ownership

| Track | Owner | Shared files | Start condition |
| --- | --- | --- | --- |
| U0 | ユーザー対応 | READMEと導入文書だけ | R0合格 |
| M0 | エンジニア2 | versionとrelease manifest | R0合格 |
| D0 | エンジニア2 | Windows配布specだけ | R0合格 |
| Gate 4監査 | 追加機能担当 | 既存計画のread-only差分監査 | R0合格 |

U0、M0、D0のownerとshared fileは一意である。R0が合格するまで、各Trackの実装は
開始しない。

## Release manifest contract

今後のRelease manifestには次を必須とする。

- release version
- tag対象commitとtree SHA
- clean / dirty
- CI run、toolchain
- runtime取得元、SHA-256、license
- artifact名、platform、size、SHA-256
- 署名者、timestamp
- Mac notary submission ID
- 第三者試験済みSHA

## 実行して合格

同じworktree、同じHEADで次を確認した。

| 分類 | command | Exit | 確認結果 |
| --- | --- | ---: | --- |
| 文書契約 | `python3 scripts/test_post_gate_c_master.py` | 0 | `post-Gate-C master contract tests passed` |
| Desktop | `python3 scripts/test-desktop-release-version.py` | 0 | `desktop release version tests passed` |
| Web | `node scripts/test-model-selection.js` | 0 | `model selection tests passed` |
| Web | `node scripts/test-settings-helpers.js` | 0 | `settings helper tests passed` |
| Web | `node scripts/test-asr-helpers.js` | 0 | `asr helper tests passed` |
| Web | `node scripts/test-management-helpers.js` | 0 | `management helper tests passed` |
| Web | `node scripts/test-pwa-assets.js` | 0 | `pwa asset tests passed` |
| Web | `node scripts/test-tts-helpers.js` | 0 | `tts helper tests passed` |
| Python | `python3 scripts/test_server_helpers.py` | 0 | `server helper tests passed` |
| Python | `python3 scripts/test_study_pack_manager.py` | 0 | `study pack manager tests passed` |
| Python | `python3 scripts/test_context_core.py` | 0 | `context core tests passed` |
| Python | `python3 scripts/test_knowledge_layer.py` | 0 | `knowledge layer tests passed` |
| Python | `python3 scripts/test_tts_engine.py` | 0 | `tts engine tests passed` |
| Desktop | `python3 scripts/test-desktop-shell-contract.py` | 0 | `desktop shell contract tests passed` |
| JavaScript構文 | `node --check web/models.js` | 0 | 構文エラーなし |
| JavaScript構文 | `node --check web/settings.js` | 0 | 構文エラーなし |
| JavaScript構文 | `node --check web/asr.js` | 0 | 構文エラーなし |
| JavaScript構文 | `node --check web/management.js` | 0 | 構文エラーなし |
| JavaScript構文 | `node --check web/app.js` | 0 | 構文エラーなし |
| JavaScript構文 | `node --check web/tts.js` | 0 | 構文エラーなし |
| JavaScript構文 | `node --check web/desktop-starting.js` | 0 | 構文エラーなし |
| Python構文 | `python3 -m py_compile server.py tts_engine.py scripts/tts_fixture_worker.py scripts/test_post_gate_c_master.py` | 0 | 構文エラーなし |
| runtime準備 | `python3 scripts/fetch-macos-python-runtime.py --archive-cache /Users/masafumimikami/Documents/desktop/Gemma4_12B/.worktrees/phase1-pc-diagnostics/build/cache --output build/macos-runtime/python` | 0 | 固定SHA-256、size、Mach-O arm64、Python 3.11.15を確認 |
| runtime準備 | `python3 scripts/stage-macos-tomos-resources.py --output build/macos-runtime/tomos` | 0 | 65ファイルとmanifestを生成 |
| runtime構文 | `python3 -m py_compile build/macos-runtime/tomos/server.py` | 0 | 構文エラーなし |
| Rust | `cargo test --manifest-path src-tauri/Cargo.toml` | 0 | 22件合格、失敗0件 |
| 差分 | `git diff --check` | 0 | 指摘なし |

`test_server_helpers.py`はsandbox内の初回実行で、一時的なlocalhost socket bindが
許可されずexit 1となった。同じコードをsocket bind可能な実行環境で再実行し、
最終結果がexit 0であることを確認した。コード不良による失敗とは判定しない。

Cargoは初回、`../build/macos-runtime/python`がなく、Rustテスト本体の開始前に
exit 101となった。固定SHA-256
`125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6`、
固定size `27241978` bytesの既存ローカルキャッシュだけでignored runtimeを準備し、
同じHEADで再実行した最終結果は22件合格、失敗0件だった。外部通信、
ユーザーPython領域への書込み、署名資源は使用していない。

## Baselineで失敗

なし。

## 環境不足で未実行

なし。初回の生成runtime不足は既存ローカルキャッシュによる準備とCargo再実行で
解消した。

## 承認待ち

なし。依存追加、外部download、ユーザーPython領域への書込み、署名資源の使用は
行っていない。

## Gate判定

**Gate R0は合格。**

確認済み:

- HEADとorigin/mainは
  `374c80186973c568ae3486bb15a9652a8a354b20`で一致。
- masterと承認済み設計の文書契約は合格。
- U0、M0、D0のownerとshared fileは一意。
- Release manifest必須項目を固定。
- Web/Python 19件とDesktop Python 3件の最終結果はすべてexit 0。
- runtime準備test 2件とruntime Python構文確認はexit 0。
- Cargoは22件合格、失敗0件。
- Baselineで失敗、環境不足で未実行、承認待ちはすべてなし。
- baseline開始前に追跡対象の変更はなく、製品コード、版番号、成果物、依存は
  変更していない。runtimeとCargo出力はGit管理対象外だけに生成した。

全合格条件を満たしたため、マスター台帳のGate R0状態だけを`検証中`から`合格`へ
変更する。U0、M0、D0は、それぞれの専用計画、専用worktree、個別Gateに従って
開始できる。
