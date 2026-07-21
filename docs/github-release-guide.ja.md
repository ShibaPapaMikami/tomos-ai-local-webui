# GitHub Release 配布手順

このプロジェクトは、GitHub Releases に Mac/Windows 用 ZIP とネイティブインストーラーを添付して配布します。アプリ本体は軽く保ち、Ollamaモデル、ComfyUI、画像モデル、ASR/OCRの大きなデータは同梱しません。

## バージョン管理方針

- タグ名は `v0.8.190` のようにアプリ版と合わせます。
- 既存 Release は上書きせず、古い ZIP を残します。
- 授業前に安定版を決め、そのタグを学生へ案内します。
- 不具合が出た場合は、前の Release ZIP へ戻せるようにします。

## 配布ZIPを作る

```sh
bash scripts/make-release-archives.sh
```

作成されるファイル:

- `dist/TOMOS_AI-vX.X.X-mac.zip`
- `dist/TOMOS_AI-vX.X.X-windows.zip`

バージョンを明示したい場合:

```sh
bash scripts/make-release-archives.sh 0.8.190
```

## ネイティブインストーラーを作る

macOS版は、`TOMOS AI.app`を`Developer ID Application`証明書で署名し、`.pkg`を`Developer ID Installer`証明書で署名して作ります。

```sh
bash scripts/make-mac-pkg.sh
```

作成されるファイル:

- `dist/TOMOS_AI-vX.X.X-mac.pkg`

公開前にApple公証を行います。

```sh
bash scripts/notarize-mac-pkg.sh dist/TOMOS_AI-vX.X.X-mac.pkg
```

この処理は署名確認、公証、チケット添付、Gatekeeper確認のいずれかが失敗すると停止します。

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

GitHub Actions の `Build native installers` を手動実行すると、`.pkg` と `.msi` の artifact を取得できます。手動実行時は `version` に `0.8.190` のようなアプリ版を入れてください。Actions の実行名、artifact 名、ジョブ概要に同じバージョンが表示されます。

## ZIPに含めるもの

- `server.py`
- `search_tools.py`
- `web/`
- 起動ファイル
- セットアップ用スクリプト
- README
- 学生向け導入手順
- リリース前チェックリスト

## ZIPに含めないもの

- `.git/`
- `ComfyUI/`
- `.venv/`
- `.venv-asr/`
- `.gemma4-data/`
- `.codegraph/`
- Ollamaモデル
- Hugging Face cache
- `*.gguf`
- `*.safetensors`
- 生成済み画像や一時ファイル

## GitHub Releaseに添付する

GitHubの Releases 画面から新しい Release を作り、ZIP とネイティブインストーラーを添付します。

GitHub CLI を使う場合の例:

```sh
gh release create v0.8.190 \
  dist/TOMOS_AI-v0.8.190-mac.zip \
  dist/TOMOS_AI-v0.8.190-windows.zip \
  dist/TOMOS_AI-v0.8.190-mac.pkg \
  dist/TOMOS_AI-v0.8.190-windows.msi \
  --title "TOMOS AI v0.8.190" \
  --notes "学生向け配布版。Mac/Windows ZIP とネイティブインストーラーを添付。"
```

実行前に `docs/release-checklist.ja.md` を確認します。

## 学生向け配布

macOSでは、Developer ID Installer署名とApple公証を通し、`spctl`で受け入れられたPKGだけを公開します。Gatekeeperの回避操作を学生へ案内しません。

Windows MSIの署名と自動更新は別の段階で整備します。
