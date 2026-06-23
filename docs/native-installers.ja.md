# ネイティブインストーラー配布メモ

Gemma4_12B は、既存の ZIP 配布を残したまま、macOS 用 `.pkg` と Windows 用 `.msi` も作れる構成にします。

## 方針

- ZIP は今後も残します。インストーラーで問題が出たときの安全な戻り先です。
- `.pkg` と `.msi` は、ZIP と同じ軽量なアプリ本体から作ります。
- Ollama モデル、GGUF、ComfyUI、Hugging Face キャッシュは同梱しません。
- モデルはアプリ内の「言語モデル」から取得します。
- 古いバージョンは GitHub Releases の古いタグに残します。

## macOS PKGを作る

macOS では Xcode Command Line Tools の `pkgbuild` を使います。

```sh
bash scripts/make-mac-pkg.sh
```

作成されるファイル:

```text
dist/Gemma4_12B-vX.X.X-mac.pkg
```

中身を確認する例:

```sh
pkgutil --payload-files dist/Gemma4_12B-vX.X.X-mac.pkg
```

インストール先は `/Applications/Gemma4_12B` です。

## Windows MSIを作る

Windows の MSI は GitHub Actions の Windows runner で作る想定です。WiX Toolset を使います。

ローカルで WiX 定義だけ確認する場合:

```sh
python3 scripts/make-windows-msi.py --no-build
```

Windows で実際に MSI を作る場合:

```powershell
dotnet tool install --global wix --version 4.0.6
python scripts/make-windows-msi.py
```

作成されるファイル:

```text
dist/Gemma4_12B-vX.X.X-windows.msi
```

MSI でインストールすると、以下の起動ショートカットを作ります。

- デスクトップ: `Gemma4 12B Web UI`
- スタートメニュー: `Gemma4 12B > Gemma4 12B Web UI`
- スタートメニュー: `Gemma4 12B > Gemma4 12B 全部起動`
- スタートメニュー: `Gemma4 12B > Gemma4 12B 重い処理を停止`

通常は `Gemma4 12B Web UI` から起動します。ComfyUI など周辺機能もまとめて起動したい場合だけ `全部起動` を使います。
ショートカットは `Gemma4_12B_Launcher.exe` を起動します。このランチャーが内部で既存の `.bat` を呼び出すため、学生が Program Files 内の `.bat` を探す必要はありません。

ZIP 版は従来どおり `.bat` を直接起動する予備配布です。

## GitHub Actionsで作る

`.github/workflows/build-installers.yml` を手動実行すると、以下の artifact ができます。
手動実行時は `version` に `0.8.190` のようなアプリ版を入れてください。Actions の実行名、artifact 名、ジョブ概要に同じバージョンが表示されます。

- `gemma4-mac-pkg-X.X.X`
- `gemma4-windows-msi-X.X.X`

Release に添付する基本セット:

- `Gemma4_12B-vX.X.X-mac.zip`
- `Gemma4_12B-vX.X.X-windows.zip`
- `Gemma4_12B-vX.X.X-mac.pkg`
- `Gemma4_12B-vX.X.X-windows.msi`

## 注意

- 現時点の `.pkg` / `.msi` は未署名です。macOS や Windows で警告が出る可能性があります。
- 販売版では署名、公証、自動更新を別途整備します。
- モデルを同梱しないため、初回起動後に必要なモデルをアプリ内で取得します。
