# GitHub Release 配布手順

このプロジェクトは、GitHub Releases に Mac/Windows 用 ZIP を添付して配布します。アプリ本体は軽く保ち、Ollamaモデル、ComfyUI、画像モデル、ASR/OCRの大きなデータは同梱しません。

## バージョン管理方針

- タグ名は `v0.8.189` のようにアプリ版と合わせます。
- 既存 Release は上書きせず、古い ZIP を残します。
- 授業前に安定版を決め、そのタグを学生へ案内します。
- 不具合が出た場合は、前の Release ZIP へ戻せるようにします。

## 配布ZIPを作る

```sh
bash scripts/make-release-archives.sh
```

作成されるファイル:

- `dist/Gemma4_12B-vX.X.X-mac.zip`
- `dist/Gemma4_12B-vX.X.X-windows.zip`

バージョンを明示したい場合:

```sh
bash scripts/make-release-archives.sh 0.8.189
```

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

GitHubの Releases 画面から新しい Release を作り、作成した2つのZIPを添付します。

GitHub CLI を使う場合の例:

```sh
gh release create v0.8.189 \
  dist/Gemma4_12B-v0.8.189-mac.zip \
  dist/Gemma4_12B-v0.8.189-windows.zip \
  --title "Gemma4_12B v0.8.189" \
  --notes "学生向け配布版。Mac/Windows ZIPを添付。"
```

実行前に `docs/release-checklist.ja.md` を確認します。

## 明日の授業向けの現実的な配布

`.pkg`、`.dmg`、`.msi` の本格インストーラーは署名や検証に時間がかかります。明日使うなら、まずは GitHub Release ZIP が安全です。

次の段階で、Tauri/Electron を使った独自デスクトップアプリ化、署名付きインストーラー、自動更新へ進めます。
