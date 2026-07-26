# TOMOS macOSポータブルアプリ・署名済みPKG設計

## 決定

TOMOS `0.8.233` は、Apple Silicon専用の最初の配布可能なTauriアプリとして作る。

Phase 3合格版を基準に、Phase 4より先に次の4工程を直列実行する。

```text
Desktop B1 ポータブルruntime
  -> Desktop B2 localhost API保護
  -> Desktop B3 app dataと旧データ移行
  -> Desktop C macOS署名・公証・PKG
```

各工程は独立したテストとGateを持つ。B1からB3がすべて合格するまで署名、公証、既存アプリへの上書きインストールを行わない。

## 目的

- `/Applications/TOMOS AI.app` を開くだけで、ブラウザーを表示せずTOMOSを利用できる。
- 利用者へPythonの事前インストールや開発リポジトリを要求しない。
- localhost APIを、別のWebページや別プロセスから無断で変更操作されにくい構成にする。
- Knowledge、Memory、教材パックなどのユーザーデータをアプリ更新から分離する。
- 旧データを削除せず、内容を確認してからコピー移行できる。
- Developer ID署名、Apple公証、staple、Gatekeeper確認済みのPKGを作る。

## 対象と対象外

### 対象

- macOS 13以降
- Apple Silicon `arm64`
- TOMOS `0.8.233`
- Tauriアプリ、Python 3.11 runtime、既存 `server.py` と `web/`
- localhost API session、app-managed data、読み取り・プレビュー・承認・コピー移行
- Developer ID Application / Installer署名、Apple公証、PKG

### 対象外

- Intel Mac
- Windows MSI
- 自動更新
- Ollama本体またはモデルの同梱
- Phase 4 Markdown Skill Manager
- VibeVoice、Qwen3-TTSなどの実モデル同梱
- 旧データ、旧アプリ、モデルの自動削除
- GitHub Releaseへの公開

## 採用方式

### 採用: Python runtimeをTauri appへ同梱

取得物を次へ固定する。

| 項目 | 固定値 |
| --- | --- |
| 配布元 | `astral-sh/python-build-standalone` GitHub Releases |
| Release | `20260718` |
| Python | `3.11.15` |
| OS / CPU | `aarch64-apple-darwin` |
| Artifact | `cpython-3.11.15+20260718-aarch64-apple-darwin-install_only.tar.gz` |
| Size | `27,241,978 bytes` |
| SHA-256 | `125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6` |

build scriptはキャッシュ済みartifactを優先し、存在しない場合だけ明示したURLから取得する。SHA-256不一致、CPU不一致、Python `3.11.x`不一致なら展開も署名も行わず停止する。

取得物のライセンスと同梱ライセンス一覧を配布候補へ含める。秘密情報、Cookie、APIキーはartifactやbuild logへ含めない。

### 不採用: system Python

現在のPoCは `python3` とコンパイル時のリポジトリ位置へ依存している。これは開発Macでは動いても別Macで同じ動作を保証できないため、配布版では使わない。

### 不採用: Rustへの全面移植

既存のKnowledge、Memory、教材パック、検索、契約書処理を一度に置き換える必要があり、今回の配布目的を超えるため行わない。

## 完成時のapp構造

```text
TOMOS AI.app/
  Contents/
    MacOS/
      tomos-desktop
    Resources/
      tomos/
        server.py
        search_tools.py
        agent_reach_adapter.py
        pdf_reader.py
        knowledge_layer.py
        context_core.py
        contract_ledger.py
        sarashina_ocr_runner.py
        study_pack_manager.py
        tts_engine.py
        packages/
        web/
        scripts/
        docs/
      python/
        bin/python3
        lib/
        LICENSE*
      THIRD_PARTY_NOTICES.md
    Info.plist
```

`src-tauri/tauri.conf.json` のbundle resourcesに必要ファイルだけを明示する。`.git/`、worktree、`dist/`、モデル、Knowledge DB、Memory DB、ログ、キャッシュ、秘密情報はappへ含めない。

## Desktop B1: ポータブルruntime

### resource root

開発時は `TOMOS_RESOURCE_ROOT` を明示した場合だけ既存rootを利用できる。配布appではTauriのresource directoryから `Resources/tomos/server.py` を解決する。

コンパイル時の `CARGO_MANIFEST_DIR` はテスト専用fallbackへ降格し、release buildでは利用しない。resource rootがapp bundle外、symlink、または必要ファイル不足なら起動を拒否する。

### Python

配布appは `Resources/python/bin/python3` だけを起動する。release buildではPATH上の `python3` へfallbackしない。

起動前に次を検証する。

- 実行ファイルがapp bundle内にある。
- symlink解決後もapp bundle内にある。
- CPUが`arm64`である。
- `python3 --version`が`3.11.x`である。
- `server.py`、`web/index.html`、必須Python moduleが存在する。

### 子プロセス

Pythonへ渡す引数は固定する。

```text
server.py --host 127.0.0.1 --port 54876
```

環境変数は許可リスト方式で渡す。アプリ終了時はアプリが起動したPython PIDだけを停止し、既存TOMOS、Ollama、別プロセスを停止しない。

標準出力と標準エラーは、会話本文や秘密情報を含めない診断ログへ送る。ログはローテーションし、ユーザーが診断情報を開いた時だけ場所を表示する。

## Desktop B2: localhost API保護

### session token

Rust側で起動ごとに32 byteの暗号学的乱数を生成し、hex文字列へ変換する。乱数生成には承認済みのRust `getrandom` crateを直接依存として使う。

tokenは次の範囲だけで保持する。

- Rustプロセスのmemory
- Rustから起動したPython子プロセスの環境変数
- Tauri WebViewの初期化script

tokenをファイル、localStorage、ログ、URL、Memory、Knowledgeへ保存しない。

### request

Tauri WebViewの共通fetch wrapperは、`/api/` へのsame-origin requestへ `X-TOMOS-Session` headerを付ける。

desktop sessionが有効なserverは次を検証する。

- bind先が`127.0.0.1`
- `Host`が`127.0.0.1:54876`または`localhost:54876`
- 状態変更requestの`X-TOMOS-Session`が一致
- JSON endpointの`Content-Type`が`application/json`
- 許可していない`Origin`を拒否

GETのhealth、静的asset、明示した読み取り専用endpointはtokenなしで利用できる。POST、削除、保存、install、download開始、workspace write、Memory変更、Knowledge indexなどの状態変更はtoken不一致時に`403`を返す。

ブラウザーfallbackは残すが、desktop session中の状態変更はアプリからだけ許可する。アプリが起動していない通常ブラウザー版では、現行のlocalhost-only境界と既存確認UIを維持する。

## Desktop B3: app dataと移行

### 書き込み先

ユーザーが生成するデータは次へ集約する。

```text
~/Library/Application Support/com.shibapapastudio.tomos-ai/
```

配下を責務別に分ける。

```text
data/
  knowledge/
  memory/
  contracts/
  study-packs/
  workspace-settings/
logs/
migration/
```

app bundle内は読み取り専用として扱う。アプリ更新でdata directoryを削除または初期化しない。

### 移行

移行は次の順序を固定する。

```text
検出
  -> 読み取り専用プレビュー
  -> 件数・容量・更新日時・移行対象を表示
  -> ユーザー承認
  -> staging directoryへコピー
  -> schema・件数・hash検証
  -> atomic renameで反映
  -> 完了記録
```

元データは削除、移動、上書きしない。コピー途中で失敗した場合はstagingだけを破棄し、現在利用中のdata directoryと元データを維持する。

自動検出対象は、既存TOMOSが使用していた明示済みの既知pathだけに限定する。任意のホームディレクトリ探索や全ディスク走査は行わない。

localStorageはWebKitアプリ領域とブラウザー領域を直接操作しない。既存ブラウザー画面から明示的にexportし、アプリで内容をプレビューしてimportする方式を採用する。`gemma4.*` のキー名と意味は変更しない。

### rollback

- app更新前のdata snapshotを1世代だけ保持する。
- rollbackはユーザー操作で実行する。
- rollbackでも元データを削除しない。
- schema versionが新しいdataを古いappで無理に開かない。

## Desktop C: 署名・公証・PKG

### 識別子

| 項目 | 値 |
| --- | --- |
| App name | `TOMOS AI` |
| Version | `0.8.233` |
| Bundle ID | `com.shibapapastudio.tomos-ai` |
| PKG identifier | `jp.local.gemma4-12b` |
| Install path | `/Applications/TOMOS AI.app` |
| Minimum macOS | `13.0` |
| Architecture | `arm64` |

### 署名順序

次の内側から外側の順で署名する。

1. Python executable、dynamic library、拡張module
2. Tauri executable
3. `TOMOS AI.app`
4. Installer PKG

appはDeveloper ID Application、PKGはDeveloper ID Installerを使う。hardened runtimeとtimestampを有効にする。署名後は`codesign --verify --deep --strict`、`pkgutil --check-signature`を実行する。

### 公証

保存済みnotary profile `tomos-notary`を使ってPKGを提出する。

```text
notarytool submit --wait
  -> Accepted
  -> stapler staple
  -> stapler validate
  -> spctl -a -vv -t install
```

いずれかが失敗した成果物は配布、インストール、公開しない。

### インストール境界

- PKG完成前に `/Applications/TOMOS AI.app` を上書きしない。
- 既存 `/Applications/Gemma4_12B` を削除しない。
- 既存モデル、Knowledge、Memory、教材パックを削除しない。
- PKG完成後も、実機へのインストールはDirectorの別承認を必要とする。
- GitHub Release公開はさらに別承認を必要とする。

## Build manifest

配布候補ごとに機械可読manifestを生成する。

```json
{
  "appVersion": "0.8.233",
  "architecture": "arm64",
  "pythonVersion": "3.11.15",
  "pythonArtifact": "cpython-3.11.15+20260718-aarch64-apple-darwin-install_only.tar.gz",
  "pythonSha256": "125587d03495bebdf30ec9e549a8469c97c0925d863ff401f24f157fd44d91d6",
  "bundleId": "com.shibapapastudio.tomos-ai",
  "pkgIdentifier": "jp.local.gemma4-12b",
  "sourceCommit": "<40文字のGit commit SHA>"
}
```

`sourceCommit`はbuild時の現在HEADから自動生成し、dirty worktreeではrelease candidate buildを拒否する。値を手入力しない。

## テストとGate

### Gate B1

- clean worktreeからarm64 app bundleを生成できる。
- app bundleを別の一時pathへ移動しても起動できる。
- PATHからPythonを除外しても同梱Pythonで起動できる。
- resource不足、CPU不一致、Python不一致を日本語エラーで停止する。
- 二重起動、port競合、owned process停止が合格する。

### Gate B2

- tokenなし、誤token、誤Host、誤Origin、誤Content-Typeの状態変更を拒否する。
- 正しいtokenの状態変更だけ成功する。
- tokenがURL、ログ、localStorage、API responseへ出ない。
- 通常ブラウザーfallbackの既存テストが合格する。

### Gate B3

- 空の新規利用者data directoryで起動できる。
- プレビュー前に書き込みが発生しない。
- 承認後のコピーと検証が成功する。
- 途中失敗で元データと現在dataを維持する。
- 同じ移行を再実行して重複しない。
- localStorage export/importが未知キーを勝手に反映しない。

### Gate C

- appとPKGの識別子、version、architectureが設計値と一致する。
- nested code、app、PKGの署名者をreadbackできる。
- 公証結果が`Accepted`である。
- staple、Gatekeeperが合格する。
- PKG内容にモデル、DB、ログ、秘密情報、`.git`が含まれない。
- インストール前のPKG SHA-256を記録する。

## 失敗時

- B1からB3の失敗は署名工程へ持ち越さない。
- 署名または公証失敗時は、PKGを`dist/rejected/`へ隔離し配布対象から除外する。
- 旧アプリを自動復旧、削除、上書きしない。
- 原因、再現手順、影響範囲、再試験条件をGate記録へ残す。

## 工程完了後

Gate C合格後にだけ、現在のMacへの上書きインストール承認を依頼する。インストール確認が合格した後、Phase 4 Markdown Skill Managerへ戻る。Intel MacとWindowsは個別設計・個別成果物として扱う。
