# Gemma 4 12B Local Web UI

[日本語](README.ja.md) / [English](README.en.md)

Gemma 4 12B を Ollama でローカル実行し、ブラウザーから使うための軽量 Web UI です。

学生や授業利用でも導入しやすいように、APIキーなしでチャット、画像入力、Web検索、ローカルフォルダーを使ったコード生成を扱える構成にしています。

## 導入方針

現時点では、Mac は `.command`、Windows は `.bat` / `.ps1` で導入・起動できる軽量構成です。将来的には以下のような本格インストーラー化も可能です。

- Mac: 署名付き `.pkg` または `.dmg`
- Windows: `.msi` または Inno Setup 形式のインストーラー

ただし配布を簡単にするには、まず現在のスクリプト方式で安定させるのが現実的です。Ollama と Python は事前インストールが必要ですが、Gemma / Qwen / Coder などのモデル取得は設定画面から実行できます。

## できること

- ローカルの Gemma 4 12B とチャット
- 画像を添付して質問
- Web検索を使った回答
- Open-Meteoを使った現在の天気・今日の予報取得
- Codex風のフォルダー/チャット管理
- 指定フォルダー内へのファイル生成・保存
- フォルダー生成の段階実行: 計画 → ファイル生成 → 保存 → 検証 → 自動修正
- 生成中の逐次表示と停止
- 応答モードの切替: 自動 / 高速 / 標準 / 精度優先
- 思考量の切替: 自動 / 軽め / 標準 / 深く
- 現在時刻、日付、曜日のローカル即答
- 短い挨拶や日常相談は軽量モデルへ自動ルーティング
- 設定画面からOllamaモデルをダウンロード
- ComfyUI がある環境では、チャットから画像生成

## 必要なもの

### 共通

- Python 3.10 以上
- Ollama
- Gemma 4 12B モデル
- 空き容量: 少なくとも 10GB 程度

Gemma 4 12B の初回ダウンロードは数GBあります。学校のネットワークでは時間がかかることがあります。
起動後に `設定` を開き、`モデルをダウンロード` から必要なモデルを取得できます。

## はじめての導入

### Mac

1. [Ollama](https://ollama.com/download) をインストールします。
2. このフォルダーを開きます。
3. ターミナルで以下を実行します。

```sh
./scripts/setup-mac.sh
```

4. 起動します。

```sh
./Start_Mac.command
```

または `Start_Mac.command` をダブルクリックします。

ターミナルがホーム `~` を開いている場合は、先にこのフォルダーへ移動してから実行します。

```sh
cd ~/Documents/desktop/Gemma4_12B
export GEMMA_CODING_MODEL="hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M"
./Gemma4_12B_全部起動.command
```

### Windows

1. [Python](https://www.python.org/downloads/) をインストールします。
   - インストール時に `Add python.exe to PATH` を有効にしてください。
2. [Ollama](https://ollama.com/download) をインストールします。
3. PowerShell でこのフォルダーへ移動し、以下を実行します。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```

4. `Start_Windows.bat` をダブルクリックします。

## 起動URL

起動後、ブラウザーで以下を開きます。

```text
http://127.0.0.1:54876
```

Mac の起動ファイルは Safari を開きます。Windows は既定ブラウザーを開きます。

## 使い方

### 通常チャット

画面下の入力欄に質問を入れて送信します。

送信方法:

- `↑` ボタン: 送信
- `■` ボタン: 生成を停止
- `Cmd + Enter`: Macで送信
- `Ctrl + Enter`: Windowsで送信
- `Enter`: 改行
- `Shift + Enter`: 改行

設定で `Enterで送信` をONにすると、Enter単体でも送信できます。日本語変換中のEnterでは送信しません。

短い挨拶や日常相談は、モデル自動時に軽量モデルへ回して速度を優先します。設計やプログラム作成では、必要に応じて精度優先・深い思考に寄せます。

`英訳して`、`和訳して`、`翻訳して` などの依頼は翻訳専用モードになります。余計な説明や箇条書きではなく、翻訳文だけを返すようにし、Web検索やフォルダー文脈を使わず軽い設定で処理します。`qwen2.5:3b` などの軽量モデルが入っている場合は翻訳だけ自動で軽量モデルを使います。固定したい場合は `GEMMA_TRANSLATION_MODEL`、または設定画面の翻訳モデルを指定してください。

### 用途別モデル

通常チャット、コード生成、翻訳で別々のOllamaモデルを使えます。設定画面でモデル名を入力すると、そのブラウザーでは入力値が優先されます。空欄に戻すとサーバー既定値に戻ります。
コード生成モデル欄には推奨候補も表示します。未取得のモデルは、設定画面の `モデルをダウンロード` から取得してください。

入力フォームの `モデル自動` から、その場で使うモデルを固定できます。`モデル自動` では通常チャット、コード生成、翻訳を用途別モデルで使い分けます。固定した場合は、次の回答から選択したモデルを使います。通常の候補は `Gemma 4`、`Qwen`、`Coder` に絞っています。
`モデル自動` のままなら、短い雑談や軽い相談は `Qwen` が入っている環境では `Qwen` を使い、調査・画像・コード・長い説明は `Gemma 4` または `Coder` を使います。軽い相談では専用の短文プロンプトを使い、会話履歴を送らずに今回の入力だけで返すため、前のコード作業文脈に引っ張られにくくなります。

フォルダー内にプログラムを作る依頼では、いきなり全コードを書かせず、まず短い実装計画を作り、ファイルごとに生成してから保存・検証します。検証で構文エラーや未完成表現が見つかった場合は、エラー内容を使って自動修正を試します。

選び方の目安:

- 通常チャット: 迷ったら `Gemma 4 12B`。速さ優先なら `Qwen 2.5 3B`。
- コード生成: すぐ使うなら `Gemma 4 12B`。複雑なフォルダー作業は `Gemma 4 Coder 12B Q4` 推奨。
- 翻訳: 通常はサーバー自動で十分。速さは `Qwen 2.5 3B`、品質優先は `Gemma 4 12B`。

| 用途 | 既定値 | 環境変数 |
| --- | --- | --- |
| 通常チャット | `gemma4:12b` | `GEMMA_MODEL` |
| コード生成 | `GEMMA_MODEL` と同じ | `GEMMA_CODING_MODEL` |
| 翻訳 | 軽量候補を自動選択 | `GEMMA_TRANSLATION_MODEL` |

コード生成用モデルを試す例:

1. 設定画面の `モデルをダウンロード` で `Gemma 4 Coder 12B Q4` を取得します。
2. `コード生成モデル` で `Gemma 4 Coder 12B Q4` を選びます。
3. フォルダー作業やプログラム作成を依頼します。

ターミナルで指定したい場合:

```bash
GEMMA_CODING_MODEL=hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M ./Gemma4_12B_Web.command
```

Windows PowerShell:

```powershell
$env:GEMMA_CODING_MODEL="hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M"
.\Gemma4_12B_Web.bat
```

`今日の天気`、`東京の天気` などの質問は Open-Meteo から直接取得します。場所を書かない場合は `GEMMA_WEATHER_LOCATION`、未設定なら `東京` を使います。

### 応答モード

入力フォーム内の選択欄、または設定画面から切り替えできます。

| モード | 用途 |
| --- | --- |
| 自動 | 内容に応じて切り替え |
| 高速 | 挨拶、短い返事、軽い質問 |
| 標準 | 普段のチャット |
| 精度優先 | 設計、調査、コード作成 |

### 思考量

設定画面から切り替えできます。

| 思考量 | 用途 |
| --- | --- |
| 自動 | 通常は標準、コード作業は深く、短文は軽め |
| 軽め | 速度優先 |
| 標準 | 速度と正確さのバランス |
| 深く | コード作成、修正、設計向け |

このUIの「思考量」は、内部思考を表示するものではありません。文脈量、履歴量、生成上限、システム指示を調整して、速度と品質のバランスを変えます。

### 画像入力

入力フォーム左側の `+` から画像を添付できます。画像のコピー&ペーストにも対応しています。

例:

```text
この画像に写っているものを説明して
このUIの問題点を教えて
```

### Web検索

右上の `Web検索` を有効にすると、DuckDuckGo HTML検索を使って検索結果を文脈に入れます。

注意:

- Web検索を使うと外部サイトへ検索リクエストが送られます。
- 高速モードでは、短い返事で検索待ちが発生しないようにWeb検索を自動で使わない設定にしています。
- Web検索中は、検索結果をまとめ切れるように通常チャットより少し長めに生成します。

### ローカル便利機能

以下のような質問はGemmaに送らず、ブラウザーのローカル情報から即答します。

```text
今の時間は？
今日の日付は？
今日は何曜日？
```

この方式にしているため、時刻のような確定情報はモデルの推測に頼りません。挨拶や日常相談は定型文ではなく、軽量モデルで生成します。

### ローカルフォルダーでコード生成

左カラムのフォルダーごとに、参照するローカルフォルダーを指定できます。

基本の流れ:

1. `+ フォルダー` でフォルダーを作ります。
2. フォルダーの `編集` から参照するローカルフォルダーを選びます。
3. 必要なファイルを文脈に追加します。
4. チャットで作成や修正を依頼します。

例:

```text
フォルダー内にシンプルなWebテトリスを作って
index.html を見やすく修正して
このCSSをスマホ対応にして
```

フォルダー作業では、コード生成用モデルにファイル内容を生成させ、保存後に構文チェックを行います。HTML内のJavaScript、単体JavaScript、JSON、CSSの基本検証に加えて、TODOや省略コード、外部CDN依存も検出します。失敗した場合は自動で修正を試します。

`簡単な`、`シンプルな`、`小さな` などの依頼では、計画生成を省略し、`Qwen` が入っている環境では `Qwen` を使って `index.html` 1ファイルを短時間で生成します。複雑なコード生成では `Gemma 4` または `Coder` を使います。

HTMLを保存した場合は、チャット結果に `動作確認` ボタンが表示されます。押すと保存したHTMLをブラウザーで確認できます。

コード生成中は、チャット内に `生成中`、`保存中`、`検証中`、`自動修正中` の進捗が表示されます。長時間止まって見える場合は `■` で停止できます。簡単生成は2分、通常のフォルダー作業は6分で区切ります。Coderモデルの初回実行は読み込みに数分かかることがあります。Coderモデルが時間内に終わらない場合は、通常のGemma 4 12Bへ自動で切り替えて再試行します。

## ComfyUI で画像生成したい場合

ComfyUI はリポジトリには含めません。GitHubに大きな外部プロジェクトやモデルを混ぜないためです。

すでに `ComfyUI/` がこのフォルダーにある場合は、以下で同時起動できます。

Mac:

```sh
./Gemma4_12B_全部起動.command
```

Windows:

```bat
Gemma4_12B_All_Start.bat
```

チャットで以下のように依頼します。

```text
赤いリンゴの画像を生成して
画像生成: rainy Tokyo alley, cinematic light, 512x512
```

任意パラメータ:

- `512x512`
- `steps=20`
- `seed=123`

通常は `steps=8` で軽く生成します。品質を上げたい場合は `steps=20` などを指定してください。

## 学習データの書き出し

設定画面の「学習データ」から、Gemmaに教えるための学習セットを作れます。

学習セットは、すぐにモデルを書き換えるものではありません。まずは「修正例」や「良い回答例」を名前つきで保存し、フォルダーに適用してチャット時のヒントとして使います。

十分に例が集まったら、「学習用ファイル」として書き出します。このファイルは、Gemmaに教えたい会話例をまとめたノートのようなものです。書き出しただけでは、まだモデルは変わりません。次の段階で中身を整え、その後ファインチューニング処理に使うと、新しいモデルを作れます。

基本の流れ:

1. 設定で学習セットを作成します。
2. Gemmaの回答下にある「修正して学習」から正しい回答を保存します。
3. 学習セットをフォルダーに適用します。
4. そのフォルダーのチャットでは、保存した修正例を参照します。
5. 例が集まったら学習用ファイルとして書き出します。
6. 次の段階で、学習用ファイルから新しいモデルを作ります。
7. 完成したモデルを設定の「モデル」から選び、チャットやフォルダーで使います。

現時点のアプリで直接できるのは 1〜5 です。6〜7 は次の実装段階で、ターミナルを使わずに画面から実行できるようにする予定です。

対象は以下から選べます。

- 現在のチャット
- 現在のフォルダー
- すべてのチャット
- 選択中の学習セット

書き出したファイルは、1行ごとに「ユーザーの質問」と「正しい回答」が入った学習用メモです。ふだんは中身を直接編集する必要はありません。

開発者向けには `JSONL` という形式で保存しています。これは、たくさんの会話例を学習処理が読み取りやすい形で並べたものです。

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}],"metadata":{"task":"translation","model":"gemma4:12b"}}
```

新しいモデルを作る前に、空行やエラー回答を取り除いて整えます。今は下のコマンドで整えますが、今後はUIから実行できるようにします。

```sh
python3 scripts/standardize_training_data.py gemma4-training-active-YYYYMMDD-HHMMSS.jsonl
```

メタ情報も残したい場合:

```sh
python3 scripts/standardize_training_data.py gemma4-training-active-YYYYMMDD-HHMMSS.jsonl --keep-metadata
```

まずは成功した翻訳、自然な短文応答、正しく保存できたコード生成など、質の良い例だけを残すのがおすすめです。

## よくあるトラブル

### Python が見つからない

Windowsでは Python インストール時に `Add python.exe to PATH` が有効になっているか確認してください。

### Ollama が見つからない

Ollama をインストールし、アプリを一度起動してください。

### 初回の返答が遅い

モデルをメモリに読み込むため、初回だけ時間がかかります。2回目以降は速くなることがあります。

### PCが重い

画像生成や大きなコード生成は負荷が高いです。重い処理を止めるには以下を使います。

Mac:

```sh
./Gemma4_12B_重い処理を停止.command
```

Windows:

```bat
Gemma4_12B_Stop_Heavy.bat
```

## 開発者向け

Web UIのみ起動:

```sh
python3 server.py --host 127.0.0.1 --port 54876
```

準備確認:

```sh
./scripts/check.sh
```

1回だけCLIで質問:

```sh
./scripts/ask.sh "日本語で短く自己紹介して"
```

主なファイル:

- `server.py`: ローカルHTTPサーバー、Ollama連携、フォルダー読み書き、天気/画像生成API
- `search_tools.py`: Web検索の取得、HTML解析、検索結果コンテキスト生成
- `web/index.html`: UI
- `web/app.js`: アプリ状態、イベント登録、各モジュールの接続
- `web/messages.js`: チャット表示
- `web/sidebar.js`: フォルダー/チャット一覧
- `web/settings.js`: 設定画面とモデル取得表示
- `web/workspace.js`: ローカルフォルダー、保存、プレビュー、コード抽出
- `web/training.js`: 学習セット、修正例、学習用ファイル書き出し
- `web/search.js`: Web検索のフロント側状態、検索結果整形、検索時の生成設定
- `web/weather.js`: 天気判定、場所抽出、現在地保存
- `web/composer.js`: 入力欄、添付画像、送信操作
- `web/styles.css`: 画面スタイル
- `scripts/test-*.js`: フロント側ヘルパーの退行テスト
- `scripts/test_search_tools.py`: サーバー側Web検索処理の退行テスト

変更後の確認:

```sh
node scripts/test-router.js && node scripts/test-workspace-helpers.js && node scripts/test-sidebar-helpers.js && node scripts/test-management-helpers.js && node scripts/test-submit-classification.js && node scripts/test-model-selection.js && node scripts/test-training-export.js && node scripts/test-weather-helpers.js && node scripts/test-settings-helpers.js && node scripts/test-search-helpers.js
python3 scripts/test_search_tools.py
python3 -m py_compile server.py search_tools.py scripts/standardize_training_data.py
```

## GitHubに含めないもの

以下は `.gitignore` で除外します。

- `ComfyUI/`
- Python仮想環境
- モデルファイル
- 生成画像
- キャッシュ
- ログ

これにより、GitHubリポジトリは軽く保てます。ComfyUIや画像モデルは、利用者が各自のPCに別途導入します。

## ライセンス

MIT License
