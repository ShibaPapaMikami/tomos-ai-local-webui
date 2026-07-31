# TOMOS音声engine比較ラボ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Complete Gate 4 before starting. Dependency installation and model download require separate Director approval.

**Goal:** VibeVoice RealtimeとQwen3-TTSを同じTTS worker contractへ接続し、日本語、開始速度、停止、PC負荷を比較して役割を決める。

**Architecture:** engine固有依存は隔離venvとadapter workerへ閉じ込める。TOMOS本体はPhase 3のJSON Lines contractだけを使い、比較中もdefault engineをoffにする。

**Tech Stack:** Phase 3 TTS contract、隔離Python venv、JSON Lines、local-only benchmark。

---

## Candidate Roles

| 候補 | 比較する役割 | 初期ラボで除外 |
| --- | --- | --- |
| VibeVoice Realtime 0.5B | 標準音声、streaming開始速度 | ASR、会議録 |
| Qwen3-TTS 0.6B | 軽量なオリジナル音声候補 | VoiceDesign、clone |
| Qwen3-TTS 1.7B | 品質優先のオリジナル音声候補 | VoiceDesign、clone |

このラボへ入れない:

- 本人、声優、第三者の音声
- VoiceDesign
- Base voice cloning
- VibeVoice ASR
- ZONOS2
- 外部TTS API
- 許諾を確認できないvoice preset

## Files

作成する:

- `integrations/tts/vibevoice_worker.py`
- `integrations/tts/qwen3_tts_worker.py`
- `integrations/tts/vibevoice-requirements.lock`
- `integrations/tts/qwen3-tts-requirements.lock`
- `integrations/tts/candidate-manifest.json`
- `scripts/prepare_tts_candidate.py`
- `scripts/test_tts_adapter_contract.py`
- `benchmarks/tts_evaluation/__init__.py`
- `benchmarks/tts_evaluation/cases.json`
- `benchmarks/tts_evaluation/run.py`
- `docs/benchmarks/tts-candidate-inventory.ja.md`
- `docs/benchmarks/tts-evaluation-results.ja.md`

変更しない:

- `server.py`
- `web/app.js`
- `web/tts.js`
- `web/index.html`
- `web/sw.js`
- Model Router
- Memory、Knowledge、Plugin

## Isolation Contract

venv:

```text
.gemma4-data/venvs/tts/vibevoice/
.gemma4-data/venvs/tts/qwen3-tts/
```

model cache:

```text
.gemma4-data/models/tts/vibevoice/
.gemma4-data/models/tts/qwen3-tts/
```

規則:

- system Pythonへpackageを追加しない。
- repoへvenv、model、download cacheをcommitしない。
- requirements lockはpackage名、exact version、SHA-256 hashを含む。
- Git sourceが必要ならrepository URLとcommit SHAをlockへ固定し、branch名を使わない。
- install commandはGate V0承認後に確定lockだけを対象に実行する。
- runtimeの外部通信は無効にし、modelは承認済みlocal pathから読む。
- model cacheを自動削除しない。
- adapterはTOMOSのlocal file、Memory、Knowledge、Pluginへアクセスしない。

Phase 3設定例:

```text
GEMMA_TTS_ENGINE=vibevoice
GEMMA_TTS_WORKER_PYTHON=.gemma4-data/venvs/tts/vibevoice/bin/python
GEMMA_TTS_WORKER=integrations/tts/vibevoice_worker.py
```

Windowsではworker Pythonを `.gemma4-data\venvs\tts\vibevoice\Scripts\python.exe` とする。設定は手動で行い、ラボ終了後は `GEMMA_TTS_ENGINE=off` に戻す。

## Candidate Manifest Contract

`integrations/tts/candidate-manifest.json`:

```json
{
  "schemaVersion": 1,
  "candidates": [
    {
      "id": "vibevoice",
      "engine": "vibevoice",
      "codeRevision": "immutable-commit-sha",
      "modelId": "official-model-id",
      "modelRevision": "immutable-model-sha",
      "requirementsLock": "integrations/tts/vibevoice-requirements.lock",
      "venvRelativePath": ".gemma4-data/venvs/tts/vibevoice",
      "modelRelativePath": ".gemma4-data/models/tts/vibevoice",
      "expectedDownloadBytes": 1,
      "allowPatterns": ["approved-relative-pattern"],
      "modelFiles": [
        {
          "path": "approved-relative-file",
          "bytes": 1,
          "sha256": "64-character-lowercase-hex"
        }
      ],
      "supportedOs": ["windows"],
      "voiceAllowlist": ["approved-preset"],
      "supportsStreaming": true
    }
  ]
}
```

実行前のmanifestでは例示値を残さず、Inventory Contractで確認した実値だけを入れる。`expectedDownloadBytes` と各file bytesは正の整数、pathはrelativeかつ `..` を含まない。SHA、lock path、model file一覧が埋まらないcandidateはmanifestへ入れない。

## Inventory Contract

候補ごとに次を一次情報から記録する。

```text
candidate
provider
repositoryUrl
revisionSha
codeLicense
modelId
modelRevisionSha
modelLicense
downloadBytes
pythonRange
torchRange
cudaRange
supportedOs
supportedHardware
runtimeExternalAccess
voicePreset
voicePresetLicense
```

規則:

- repositoryとmodelのrevisionは不変SHA。
- code licenseとmodel licenseを分ける。
- voice presetの出所と利用条件を分ける。
- Windows、macOS、Linuxを推測で対応扱いにしない。
- 17項目の1つでも不明なcandidateはinstall対象外。

## Worker Mapping

Phase 3 contractへ次のように対応させる。

| Phase 3 field | VibeVoice adapter | Qwen3-TTS adapter |
| --- | --- | --- |
| requestId | そのまま返す | そのまま返す |
| text | 1から1000文字 | 1から1000文字 |
| voice | 承認済みpreset ID | 承認済みpreset ID |
| language | ja/en/auto | ja/en/auto |
| stream=false | 完成WAV | 完成WAV |
| stream=true | PCM s16le chunk | 非対応ならerror |
| cancel | process terminationを検出して終了 | process terminationを検出して終了 |

adapter規則:

- stdinの1 JSON line以外を入力に使わない。
- stdoutはPhase 3 JSON Linesだけ。
- library logはstderr。
- textをstderrへ出さない。
- model pathとvenv pathをstdoutへ出さない。
- random seedを0に固定できる場合は固定する。
- output sample rateをstatusとstart eventで正確に返す。
- streaming非対応を擬似streamで装わない。

## Evaluation Cases

`cases.json` は10文固定。

内訳:

- 日常会話: 2文
- 数字、日時、英字混在: 2文
- 固有名詞を含まない長文: 2文
- 句読点と短い間: 2文
- 停止試験用長文: 2文

禁止:

- 実在人物名
- 会社の秘密情報
- 契約情報
- 音声clone用reference
- copyrighted台詞の長文

case:

```json
{
  "id": "ja-mixed-01",
  "text": "次の予定は7月24日、午前10時30分です。TOMOSで確認します。",
  "language": "ja",
  "expectedReadings": ["しちがつ", "じゅうじさんじゅっぷん", "トモス"],
  "maxDurationMs": 12000
}
```

発音判定は自動ASRだけで確定しない。自動ASR結果と人の5段階評価を別列で保存する。

## Task 1: Candidate inventoryとlock候補を作る

**Files:**

- Create: `docs/benchmarks/tts-candidate-inventory.ja.md`
- Create: `integrations/tts/vibevoice-requirements.lock`
- Create: `integrations/tts/qwen3-tts-requirements.lock`
- Create: `integrations/tts/candidate-manifest.json`

- [ ] **Step 1: 一次情報を確認する**

公式repository、公式model card、公式releaseだけを使い、Inventory Contractの17項目を埋める。

- [ ] **Step 2: 依存treeを確定する**

lockへ直接依存と解決後の全推移依存をexact versionとhash付きで記録する。installはまだ実行しない。

- [ ] **Step 3: package licenseを確認する**

直接依存と配布物へ含める可能性がある推移依存のlicenseを一覧化する。商用利用、再配布、voice利用条件を別に記載する。

- [ ] **Step 4: 容量と対応環境を合計する**

candidateごとにvenv、model、初回cacheの最大容量をGiBで記録する。GPU VRAMは公式最低値とTOMOS実測値を別列にする。

- [ ] **Step 5: Gate V0報告を作る**

```text
candidate:
code revision:
model revision:
code license:
model license:
voice preset license:
download GiB:
venv GiB:
supported OS:
supported GPU:
外部通信:
削除方法:
```

全項目を実値で埋める。不明欄があるcandidateは承認対象へ入れない。

## Gate V0: Install・Download承認

Directorがcandidateごとにlock、revision、license、容量、実行PCを承認するまでTask 2以降へ進まない。

承認は隔離venvへのinstallとmodel downloadだけに適用し、release同梱、標準engine化、voice cloneを許可しない。

## Task 2: 承認済みcandidateを隔離準備する

**Files:**

- Create: `scripts/prepare_tts_candidate.py`
- Create: `scripts/test_tts_adapter_contract.py`
- Read: `integrations/tts/candidate-manifest.json`

- [ ] **Step 1: prepare scriptの失敗testを作る**

fake subprocessとfake downloaderで次を検証する。

- manifestにないcandidateを拒否する。
- confirm文字列がcandidate IDと一致しない時はnetwork call 0回。
- venv pathが `.gemma4-data/venvs/tts/` 外なら拒否する。
- model pathが `.gemma4-data/models/tts/` 外なら拒否する。
- pip commandはvenv Python、`--require-hashes`、承認lockを使う。
- model IDとrevisionはmanifest値だけを使う。
- tokenを引数、stdout、fileへ保存しない。
- delete commandが存在しない。

- [ ] **Step 2: prepare scriptを実装する**

CLI:

```bash
python3 scripts/prepare_tts_candidate.py --candidate vibevoice --confirm-candidate vibevoice
python3 scripts/prepare_tts_candidate.py --candidate qwen3-tts --confirm-candidate qwen3-tts
```

処理順:

1. manifestを読む。
2. candidate ID、revision、license、downloadBytes、venv path、model pathを表示する。
3. `--confirm-candidate` の完全一致を確認する。
4. `python3 -m venv` を引数配列で実行する。
5. venv Pythonで `-m pip install --require-hashes -r <approved-lock>` を実行する。
6. venv内の承認済みprovider downloaderへmanifestのmodel ID、revision SHA、local directory、allowPatternsを渡す。
7. download後のfile相対path、size、SHA-256をmanifestと照合する。
8. 全一致時だけ `prepared.json` をmodel directoryへatomic保存する。

規則:

- shellを使わない。
- downloader telemetryを無効にする。
- public artifactだけを扱う。認証tokenが必要なら停止する。
- 予定downloadBytesを10%以上超えたら停止する。
- hash不一致時はreadyにしない。取得済みfileを自動削除しない。
- 再実行時はprepared.jsonと実file hashが一致すればnetwork callを行わない。

- [ ] **Step 3: testと構文を合格させる**

```bash
python3 scripts/test_tts_adapter_contract.py
python3 -m py_compile scripts/prepare_tts_candidate.py
```

期待結果: networkを使わないfake testが終了コード0。

- [ ] **Step 4: Gate V0で承認されたcandidateだけを準備する**

実行前にGate V0報告とmanifest SHA-256を再確認する。承認されていないcandidate commandを実行しない。

## Task 3: Adapter contract testを作る

**Files:**

- Modify: `scripts/test_tts_adapter_contract.py`
- Read: `scripts/tts_fixture_worker.py`
- Read: `scripts/test_tts_engine.py`

- [ ] **Step 1: fake adapter testを先に作る**

engine固有libraryをimportせず、adapter moduleへfake backendを注入して次を検証する。

- requestIdが一致。
- stream=falseは有効WAV。
- streaming対応adapterはstart、連続sequence、done。
- streaming非対応adapterはerror。
- text 1001文字を拒否。
- 未承認voice presetを拒否。
- stdoutにJSON以外がない。
- cancel相当のBrokenPipeで終了する。
- model path、text、tracebackをstdoutへ出さない。

- [ ] **Step 2: adapter未作成失敗を確認する**

```bash
python3 scripts/test_tts_adapter_contract.py
```

期待結果: adapter module不在で失敗。

## Task 4: VibeVoice adapterを実装する

**Files:**

- Create: `integrations/tts/vibevoice_worker.py`
- Modify: `scripts/test_tts_adapter_contract.py`

- [ ] **Step 1: backend境界を作る**

adapter内でengine importを行う関数とJSON Lines入出力を分ける。testではengine import関数をfakeへ差し替える。

- [ ] **Step 2: non-streamingを接続する**

Phase 3のstream=false responseへWAV、durationMs、sampleRateを返す。

- [ ] **Step 3: streamingを接続する**

upstreamが生成したPCM chunkを変換せずに返せる場合だけstream=trueを実装する。sample formatがfloatの場合はclip後にsigned 16-bit little-endianへ変換する。

- [ ] **Step 4: voice allowlistを実装する**

Inventoryで承認されたpreset IDだけを定数allowlistにする。requestからfile pathやreference audioを受け取らない。

- [ ] **Step 5: contract testを合格させる**

```bash
python3 scripts/test_tts_adapter_contract.py
python3 -m py_compile integrations/tts/vibevoice_worker.py
```

期待結果: engineをloadしないfake testが終了コード0。

## Task 5: Qwen3-TTS adapterを実装する

**Files:**

- Create: `integrations/tts/qwen3_tts_worker.py`
- Modify: `scripts/test_tts_adapter_contract.py`

- [ ] **Step 1: 0.6Bと1.7Bを設定で分ける**

adapter起動時に承認済みmodel IDを環境設定から1つ読む。requestからmodel IDを変更できない。

- [ ] **Step 2: non-streamingを接続する**

Phase 3のstream=false responseへWAV、durationMs、sampleRateを返す。

- [ ] **Step 3: streaming対応を正直に返す**

pinned revisionの公式APIがchunk生成を提供する場合だけstream=trueを実装する。提供しない場合は `tts_streaming_unsupported`。

- [ ] **Step 4: voice allowlistを実装する**

承認済みpresetだけを許可する。reference audio、VoiceDesign prompt、clone fieldをrequest schemaへ追加しない。

- [ ] **Step 5: contract testを合格させる**

```bash
python3 scripts/test_tts_adapter_contract.py
python3 -m py_compile integrations/tts/qwen3_tts_worker.py
```

期待結果: engineをloadしないfake testが終了コード0。

## Task 6: Evaluation runnerを作る

**Files:**

- Create: `benchmarks/tts_evaluation/__init__.py`
- Create: `benchmarks/tts_evaluation/cases.json`
- Create: `benchmarks/tts_evaluation/run.py`
- Modify: `scripts/test_tts_adapter_contract.py`

- [ ] **Step 1: 10 caseを作る**

Evaluation Casesの内訳を満たし、schema testを追加する。

- [ ] **Step 2: local worker runnerを作る**

CLI:

```bash
python3 benchmarks/tts_evaluation/run.py --engine vibevoice --worker-python WORKER_PYTHON --worker integrations/tts/vibevoice_worker.py --cases benchmarks/tts_evaluation/cases.json --output-root .gemma4-data/benchmarks/tts_evaluation
```

実装規則:

- worker Pythonとworker pathは実在file。
- shellを使わない。
- 10 caseをcold、warm、LLM contentionで各1回実行する。
- first audio chunkまでのmsを計測する。
- 全体生成時間、duration、real-time factorを計算する。
- stop caseは開始1500ms後にprocessをterminateし、無音までのmsを測る。
- RSSは権限なしで取得できる時だけ計測する。
- GPU VRAMはnvidia-smiが使える時だけ計測する。
- textとaudioをresultへ保存しない。
- audioは人評価用に明示 `--save-review-audio` がある時だけ `.gemma4-data/benchmarks/tts_evaluation/review-audio/<run-id>/` へ保存する。
- review audio保存前に確認文を表示し、既定値は保存しない。

- [ ] **Step 3: runner testを追加する**

fixture workerで次を確認する。

- first chunk時間。
- sequence。
- real-time factor。
- terminate。
- audio非保存が初期値。
- resultにtext、audio、絶対pathがない。

- [ ] **Step 4: testを合格させる**

```bash
python3 scripts/test_tts_adapter_contract.py
python3 -m py_compile benchmarks/tts_evaluation/run.py
```

期待結果: 終了コード0。

## Task 7: 実機比較と人評価を行う

- [ ] **Step 1: 各candidateを同じPCで測る**

順序をVibeVoice、Qwen3-TTS 0.6B、Qwen3-TTS 1.7Bで固定し、別日に順序を逆にして温度・cache差を確認する。

- [ ] **Step 2: LLM contentionを測る**

Qwen3 4Bへ固定promptを送っている間にTTSを実行し、Qwen tokens/sec低下率を記録する。

- [ ] **Step 3: 日本語を人評価する**

評価者はengine名を隠した音声を聞き、次を1から5で評価する。

- 自然さ
- 聞き取りやすさ
- 数字、英字の正しさ
- 句読点の間
- キャラクター適合

読み間違いは件数で記録する。ASR結果と人評価を混ぜない。

- [ ] **Step 4: supported OSを実測する**

Windows CPUのみ、Windows NVIDIA、Apple Siliconについて、Inventoryで対応と確認できた組み合わせだけを試す。未対応環境へ無理にinstallしない。

- [ ] **Step 5: default engineをoffへ戻す**

各実測後にTOMOSを `GEMMA_TTS_ENGINE=off` で起動し、通常チャットが動くことを確認する。

## Task 8: 結論を保存する

**Files:**

- Create: `docs/benchmarks/tts-evaluation-results.ja.md`

- [ ] **Step 1: Phase 3の合格基準を適用する**

`docs/tts-comparison-protocol.ja.md` の標準音声候補とオリジナル音声候補の基準を変えずに使う。

- [ ] **Step 2: 役割を4値で判定する**

candidateごとの結論:

- `標準音声候補`
- `オリジナル音声候補`
- `実験継続`
- `不採用`

- [ ] **Step 3: 証拠を紐付ける**

run ID、実行PC区分、人評価件数、license、revision SHAを結論へ紐付ける。

- [ ] **Step 4: 本体採用を分離する**

候補になってもdefault engineを変更しない。installer、model取得UI、voice選択UI、再配布条件を含む別の実装計画を作る。

## Gate V1

合格条件:

- code、model、voice presetのlicenseとrevisionが固定されている。
- 隔離venv以外へ依存を追加していない。
- worker contract testがfake backendで合格。
- 実測は承認済みcandidateと対応OSだけ。
- text、audio、PC識別情報を初期状態で保存していない。
- clone、VoiceDesign、reference audioを扱っていない。
- TTS offで既存チャットが回帰していない。
- 結論にrun IDと人評価がある。

推奨commit message:

```text
test: add isolated local TTS engine evaluation adapters
```

commit、標準engine化、installer同梱、model再配布はそれぞれ別承認とする。
