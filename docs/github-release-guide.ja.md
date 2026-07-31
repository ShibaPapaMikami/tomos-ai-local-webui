# GitHub Release 配布手順

学生向けMac版は、Apple Silicon専用の公証済みTauri PKG `TOMOS_AI-v0.8.233-mac-arm64.pkg`で配布します。ZIPは初心者向けRelease assetにしません。アプリへOllama本体やOllamaモデルは同梱しないため、利用にはOllamaが別途必要です。

GitHubが自動表示する`Source code (zip)`と`Source code (tar.gz)`は削除できません。TOMOS側では追加のmacOS用ZIPを添付せず、利用者には公証済みPKGを案内します。

## バージョン管理方針

- タグ名はアプリ版に合わせ、今回のMac候補は `v0.8.233` とします。
- 既存Releaseは上書きや削除をせず、前版へ戻せる状態を保ちます。
- 授業前に安定版を決め、そのタグを学生へ案内します。
- 新規作成、asset添付、公開はDirectorの承認後に行います。

## ZIPの位置づけ

`scripts/make-release-archives.sh`が作るZIPは、旧経路の保守・調査用です。学生向けMac導入ではZIPや`.command`を案内せず、公証済みPKGだけを案内します。

## Macネイティブインストーラーを作る

Developer ID Applicationで署名したTauri appから、Developer ID Installer署名付きPKGを作ります。

```sh
bash scripts/make-macos-tauri-pkg.sh
```

作成されるファイル:

- `dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg`

公開候補はrelease gateでApple公証、チケット添付、Gatekeeper確認、SHA-256生成を一括実行します。

```sh
bash scripts/release-gate-macos-tauri.sh \
  dist/candidate/TOMOS_AI-v0.8.233-mac-arm64.pkg
```

成功時だけ、次の2ファイルが配布候補になります。

- `dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg`
- `dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg.sha256`

署名確認、公証、チケット添付、Gatekeeper確認、SHA-256確認のいずれかが失敗した成果物は配布しません。

公開前に、アプリとPKGを確認します。

```sh
codesign --verify --deep --strict --verbose=2 "/Applications/TOMOS AI.app"
pkgutil --check-signature dist/TOMOS_AI-vX.X.X-mac.pkg
xcrun stapler validate dist/TOMOS_AI-vX.X.X-mac.pkg
spctl -a -vv -t install dist/TOMOS_AI-vX.X.X-mac.pkg
```

Windows の `.msi` は GitHub Actions の Windows runner で作る想定です。ローカルでは WiX 定義だけ確認できます。

```sh
python3 scripts/make-windows-msi.py --no-build
```

Windows MSIの署名と学生向け配布はDesktop Phase Dで別途判定します。

GitHub Actionsの`Build Windows installer`を手動実行すると、MSIのartifactを取得できます。Mac版は署名証明書を登録したMacで作成・公証します。

## GitHub Releaseに添付する

GitHub Releaseへ添付するMac assetは、公証済みPKGとSHA-256ファイルだけです。ZIP、candidate PKG、未署名PKGは添付しません。

GitHub CLI を使う場合の例:

```sh
gh release create v0.8.233 \
  dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg \
  dist/notarized/TOMOS_AI-v0.8.233-mac-arm64.pkg.sha256 \
  --title "TOMOS AI v0.8.233" \
  --notes "Apple Silicon専用の公証済みMac版。Ollamaは別途必要です。"
```

これはコマンド例であり、Directorの公開承認前には実行しません。実行前に `docs/release-checklist.ja.md` を確認します。

## 学生向け配布

macOSでは、Developer ID署名、Apple公証、`stapler validate`、`spctl`、SHA-256がすべて合格したPKGだけを公開します。Gatekeeperの回避操作を学生へ案内しません。

- 対応環境はApple Silicon Macです。
- インストーラーは既存の設定、Memory、Knowledge、教材パック、旧フォルダーを削除しません。
- Ollama本体とモデルは同梱しないため、別途準備が必要です。
- 現在Macへの上書きインストールは、実機確認の別承認後に行います。
