# Nemotron 3.5 ASR セットアップメモ

目的: 音声入力ボタンで録音した音声を、NVIDIA Nemotron 3.5 ASR で文字起こしする。

## 現在できること

- Web UIは最初から `nvidia/nemotron-3.5-asr-streaming-0.6b` をASR候補にします。
- 音声ボタンで録音した音声を `/api/asr/transcribe` に送ります。
- サーバーは `GEMMA_ASR_RUNNER` に指定した外部ランナーへ音声ファイルを渡します。
- `scripts/asr_nemotron_runner.py` はNeMoが導入済みならNemotronで文字起こしを試します。

## まだ必要なもの

NemotronはNeMo/PyTorch前提のモデルです。ブラウザ録音はWebMになることが多いため、WAV変換用に `ffmpeg` も必要です。

- Python 3.11 以上
- PyTorch
- Cython
- packaging
- NVIDIA NeMo main/26.06相当
- ffmpeg

注意: 通常の `pip install "nemo_toolkit[asr]"` だけでは、Nemotron 3.5 ASRが必要とする
`nemo.collections.asr.models.rnnt_bpe_models_prompt` が入らない場合があります。
その場合は設定画面で「Nemotron対応NeMo」が不足として表示されます。

## 起動時の設定

Macの起動ファイルでは、以下を自動で設定します。

```bash
GEMMA_ASR_MODEL=nvidia/nemotron-3.5-asr-streaming-0.6b
GEMMA_ASR_RUNNER="python3 scripts/asr_nemotron_runner.py"
GEMMA_ASR_LANGUAGE=ja-JP
```

Windowsの起動ファイルでは、同じ内容を `python scripts/asr_nemotron_runner.py` で設定します。

## Macで試す準備

依存の導入は重いため、自動では実行しません。必要な場合だけ次を実行します。

```bash
./scripts/setup-asr-nemotron-mac.sh
```

Macでは、利用できる場合は Homebrew の Python 3.12 を優先します。`pyenv` のPythonで `hashlib.blake2b` が使えない環境では、NeMoの読み込み中に失敗するためです。

完了後、ASR用venvのPythonを使う場合は次のように起動します。

```bash
GEMMA_ASR_RUNNER=".venv-asr/bin/python scripts/asr_nemotron_runner.py" ./Gemma4_12B_Web.command
```

## Windowsで試す準備

WindowsではPC環境差が大きいため、まず手動導入を推奨します。

```bat
python -m venv .venv-asr
.venv-asr\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install Cython packaging
python -m pip install torch torchaudio
python -m pip install "nemo_toolkit[asr] @ git+https://github.com/NVIDIA/NeMo.git@main"
```

ffmpegも別途インストールしてPATHへ追加してください。導入後は、起動前に次を設定します。

```bat
set GEMMA_ASR_RUNNER=.venv-asr\Scripts\python.exe scripts\asr_nemotron_runner.py
Gemma4_12B_Web.bat
```

## 動作の流れ

1. 音声ボタンを押す。
2. ブラウザで録音する。
3. Web UIが録音データとASRモデル名をサーバーへ送る。
4. サーバーが録音データを一時ファイルに保存する。
5. `GEMMA_ASR_RUNNER` のスクリプトを呼び出す。
6. Nemotronが文字起こしできたら、結果を入力欄へ入れる。

## 注意

NeMoやPyTorchの導入は重いため、学生向けインストーラーでは任意機能として扱うのが安全です。導入前でも通常チャット、Web検索、画像、フォルダー操作は使えます。
