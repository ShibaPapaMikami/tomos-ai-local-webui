# ネイティブインストーラー配布メモ

Gemma4_12B は、既存の ZIP 配布を残したまま、macOS 用 `.pkg` と Windows 用 `.msi` も作れる構成にします。

## 方針

- ZIP は今後も残します。インストーラーで問題が出たときの安全な戻り先です。
- `.pkg` と `.msi` は、ZIP と同じ軽量なアプリ本体から作ります。
- Ollama モデル、GGUF、ComfyUI、Hugging Face キャッシュは同梱しません。
- モデルはアプリ内の「言語モデル」から取得します。
- 古いバージョンは GitHub Releases の古いタグに残します。

## macOS PKGを署名して作る

macOS版は、`TOMOS AI.app`を`Developer ID Application`証明書で署名します。配布するPKGは、別の`Developer ID Installer`証明書で署名します。どちらかの証明書がない場合、未署名のアプリやPKGは作成・配布しません。

```sh
bash scripts/make-mac-pkg.sh
```

作成されるファイル:

```text
dist/TOMOS_AI-vX.X.X-mac.pkg
```

中身を確認する例:

```sh
pkgutil --check-signature dist/TOMOS_AI-vX.X.X-mac.pkg
```

Apple公証用の認証情報をキーチェーンへ`tomos-notary`として登録したMacでは、次のコマンドで公証、チケット添付、Gatekeeper確認まで実行します。

```sh
bash scripts/notarize-mac-pkg.sh dist/TOMOS_AI-vX.X.X-mac.pkg
```

インストール先は `/Applications/TOMOS AI.app` です。

インストール後は、「アプリケーション」の「TOMOS AI」を開きます。LaunchpadやDockからも起動できます。

Ollamaが未導入の場合は、TOMOS AIが案内を表示します。「Ollamaを入れる」を押して公式インストーラーを入れた後、TOMOS AIをもう一度開いてください。導入済みのOllamaはTOMOS AIが自動で見つけて起動するため、ターミナル操作や接続URLの入力は不要です。

以前の `/Applications/Gemma4_12B` は自動削除されません。新しい「TOMOS AI」で設定、長期記憶、教材パックを確認した後に、古いフォルダーを手動でゴミ箱へ移動してください。

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
dist/TOMOS_AI-vX.X.X-windows.msi
```

MSI でインストールすると、以下の起動ショートカットを作ります。

- デスクトップ: `TOMOS AI Web UI`
- スタートメニュー: `TOMOS AI > TOMOS AI Web UI`
- スタートメニュー: `TOMOS AI > TOMOS AI 全部起動`
- スタートメニュー: `TOMOS AI > TOMOS AI 重い処理を停止`

通常は `TOMOS AI Web UI` から起動します。ComfyUI など周辺機能もまとめて起動したい場合だけ `全部起動` を使います。
ショートカットは `Gemma4_12B_Launcher.exe` を起動します。このランチャーが内部で既存の `.bat` を呼び出すため、学生が Program Files 内の `.bat` を探す必要はありません。

ZIP 版は従来どおり `.bat` を直接起動する予備配布です。

## GitHub Actionsで作る

`.github/workflows/build-installers.yml` を手動実行すると、Windows用MSIのartifactを作れます。公開用Mac PKGは、署名証明書を登録したMacで作成・公証します。
手動実行時は `version` に `0.8.190` のようなアプリ版を入れてください。Actions の実行名、artifact 名、ジョブ概要に同じバージョンが表示されます。

- `tomos-ai-windows-msi-X.X.X`

Release に添付する基本セット:

- `TOMOS_AI-vX.X.X-mac.zip`
- `TOMOS_AI-vX.X.X-windows.zip`
- `TOMOS_AI-vX.X.X-mac.pkg`
- `TOMOS_AI-vX.X.X-windows.msi`

## 注意

- macOS PKGはDeveloper ID Installer署名とApple公証を通したものだけを公開します。
- Windows MSIの署名は別途整備が必要です。Windowsで警告が出る可能性があります。
- モデルを同梱しないため、初回起動後に必要なモデルをアプリ内で取得します。

## 内部名の互換性

macOSのインストール先は `/Applications/TOMOS AI.app` へ移行しました。既存ユーザーとの互換を優先し、以下の内部名は当面 `Gemma4_12B` のまま維持します。

- Windows の内部インストールフォルダー
- Windows ランチャー名: `Gemma4_12B_Launcher.exe`
- ZIP 内の起動ファイル名: `Gemma4_12B_Web.*`、`Gemma4_12B_All_Start.bat`
- 環境変数や保存キーの `GEMMA_*` / `gemma4.*`

将来 `TOMOS_AI` / `TOMOS AI` へ内部名も移行する場合は、別フェーズとして扱います。

移行時の必須条件:

- 既存インストール済みユーザーがアップデートできること
- 旧 `/Applications/Gemma4_12B` を残した状態でも、新しいアプリが起動できること
- Windows MSI の UpgradeCode / ProductCode / install directory の扱いを事前に決めること
- 旧ショートカット、旧フォルダー、旧ランチャーが残っても起動不能にならないこと
- `.gemma4-data`、`gemma4.*` localStorage、既存チャット履歴、教材パック、契約台帳を壊さないこと
- 失敗時に旧 `Gemma4_12B` 構成へ戻せること

この移行では、表示名の変更とは別に、インストーラーのアップグレード検証が必要です。
そのため、通常の小規模リリースとは分けて、テスト用バージョンで確認してから公開します。
