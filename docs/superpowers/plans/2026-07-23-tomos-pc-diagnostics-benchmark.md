# TOMOS PC診断・短時間ベンチマーク Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Complete Gate A before starting.

**Goal:** TOMOSがPCの理論性能を安全に診断し、ユーザー操作時だけ取得済みモデルの短い実測を行えるようにする。

**Architecture:** OS情報の読み取り、推薦計算、モデル実測を別の純粋関数とAPIに分ける。理論推薦は起動時のhealth payloadに残し、実測は明示的なPOSTだけで実行する。

**Tech Stack:** Python 3.11標準ライブラリ、Ollama local API、既存JavaScript UI。

---

## Safety Contract

- localhostのOllama以外へ送信しない。
- モデルを取得、更新、削除しない。
- ベンチ対象は `availableModels` にあり、`PULLABLE_MODELS` の `allowAutoSelect` がtrueのモデルだけ。
- ベンチマークは画面のボタン押下時だけ実行する。
- CPU、RAM、GPU情報をMemory、Knowledge、外部ログへ保存しない。
- 推薦結果で既存の選択モデルを自動変更しない。
- `llmfit` のバイナリ、依存、通信処理を組み込まない。

## Public Contract

`pc_diagnostics_payload()` の既存フィールドを維持し、次を追加する。

```json
{
  "system": {
    "gpuInfo": {
      "detected": true,
      "name": "NVIDIA GeForce RTX 4060",
      "vendor": "nvidia",
      "vramGb": 8,
      "vramConfidence": "high",
      "unifiedMemory": false,
      "source": "nvidia-smi"
    }
  },
  "recommendation": {
    "basis": "theoretical"
  },
  "benchmark": null
}
```

`POST /api/diagnostics/model-benchmark` のrequest:

```json
{
  "model": "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL"
}
```

成功response:

```json
{
  "ok": true,
  "benchmark": {
    "model": "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL",
    "elapsedMs": 1200,
    "loadMs": 300,
    "promptTokens": 8,
    "outputTokens": 24,
    "tokensPerSecond": 20.0,
    "status": "complete"
  }
}
```

拒否response:

```json
{
  "ok": false,
  "error": "benchmark_model_not_allowed"
}
```

## Task 1: RAM・GPU情報パーサーをテスト先行で追加する

**Files:**

- Modify: `server.py:3565-3678`
- Test: `scripts/test_server_helpers.py:964-1027`

- [ ] **Step 1: 失敗テストを追加する**

次のテスト関数を `scripts/test_server_helpers.py` に追加し、末尾の直接実行一覧から呼ぶ。

```python
def test_memory_gb_from_bytes() -> None:
    assert server.memory_gb_from_bytes("17179869184") == 16
    assert server.memory_gb_from_bytes("") == 0
    assert server.memory_gb_from_bytes("-1") == 0


def test_parse_nvidia_smi_gpu() -> None:
    gpu = server.parse_nvidia_smi_gpu("NVIDIA GeForce RTX 4060, 8188\n")
    assert gpu == {
        "detected": True,
        "name": "NVIDIA GeForce RTX 4060",
        "vendor": "nvidia",
        "vramGb": 8,
        "vramConfidence": "high",
        "unifiedMemory": False,
        "source": "nvidia-smi",
    }


def test_parse_windows_video_controllers() -> None:
    gpu = server.parse_windows_video_controllers(
        '[{"Name":"AMD Radeon 780M","AdapterRAM":4294967296}]'
    )
    assert gpu["detected"] is True
    assert gpu["name"] == "AMD Radeon 780M"
    assert gpu["vendor"] == "amd"
    assert gpu["vramGb"] == 4
    assert gpu["vramConfidence"] == "estimated"
    assert gpu["source"] == "powershell"


def test_local_gpu_info_unknown_shape() -> None:
    assert server.unknown_gpu_info() == {
        "detected": False,
        "name": "",
        "vendor": "unknown",
        "vramGb": 0,
        "vramConfidence": "unknown",
        "unifiedMemory": False,
        "source": "unavailable",
    }
```

- [ ] **Step 2: テストが未実装で失敗することを確認する**

```bash
python3 scripts/test_server_helpers.py
```

期待結果: `AttributeError` で `memory_gb_from_bytes` が未定義。

- [ ] **Step 3: 最小実装を追加する**

`server.py` に `memory_gb_from_bytes(value: str | int) -> int`、
`unknown_gpu_info() -> dict[str, object]`、
`parse_nvidia_smi_gpu(output: str) -> dict[str, object]`、
`parse_windows_video_controllers(output: str) -> dict[str, object]`、
`local_gpu_info() -> dict[str, object]` を追加する。

実装規則:

- macOS RAMは既存 `sysctl -n hw.memsize` を使う。
- Linux RAMは `os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")` を使う。
- Windows RAMは `powershell -NoProfile -NonInteractive -Command (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory` を引数配列で実行する。
- RAM probeのtimeoutは2秒、取得不能時は0を返す。
- byteからGiBへの変換は `round(bytes / 1024 ** 3)` とし、負数と非数値は0。
- NVIDIAは `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` を引数配列で実行する。
- Windows fallbackは `powershell -NoProfile -NonInteractive -Command Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress` を引数配列で実行する。
- timeoutは各2秒。
- shellを使わない。
- 例外、空出力、0 VRAMでは `unknown_gpu_info()` を返す。
- Apple Siliconは `name="Apple Silicon GPU"`、`vendor="apple"`、`vramGb=memoryGb`、`vramConfidence="unified"`、`unifiedMemory=true`、`source="system"` とする。
- NVIDIA nvidia-smi値は `vramConfidence="high"`、Windows CIM値は `vramConfidence="estimated"`、未検出は `vramConfidence="unknown"` とする。
- Windows CIMのAdapterRAMが0以下または64 GiB超なら値を採用しない。
- NVIDIA複数GPUではVRAMが最大の1台だけを表示する。
- Windows JSONが配列でも単一objectでも処理する。

- [ ] **Step 4: 診断payloadへ追加する**

`local_pc_system_info()` は `gpuInfo` を追加し、互換性のため既存の `gpu` と `hasGpu` も残す。

`pc_diagnostics_recommendation()` は既存戻り値へ `"basis": "theoretical"` を追加する。

`pc_diagnostics_payload()` は既存戻り値へ `"benchmark": None` を追加する。

- [ ] **Step 5: テストを合格させる**

```bash
python3 scripts/test_server_helpers.py
python3 -m py_compile server.py
```

期待結果: 両方終了コード0。

## Task 2: ベンチマーク許可判定と計測を追加する

**Files:**

- Modify: `server.py:1535-1565`
- Modify: `server.py:3670-3695`
- Modify: `server.py:6281-6460`
- Test: `scripts/test_server_helpers.py`

- [ ] **Step 1: 許可判定の失敗テストを追加する**

```python
def test_model_benchmark_rejects_uninstalled_or_hidden_model() -> None:
    assert server.model_benchmark_allowed("missing:latest", {"qwen:latest"}) is False
    assert server.model_benchmark_allowed("hf.co/huihui-ai/unsafe:latest", {"hf.co/huihui-ai/unsafe:latest"}) is False


def test_model_benchmark_allows_installed_auto_select_model() -> None:
    installed = {server.QWEN3_2507_MODEL}
    assert server.model_benchmark_allowed(server.QWEN3_2507_MODEL, installed) is True
```

実際のhidden model assertionには `PULLABLE_MODELS` 内で `allowAutoSelect` がfalseの既存IDを使う。

- [ ] **Step 2: 計測の失敗テストを追加する**

```python
def test_run_local_model_benchmark_shape() -> None:
    response = {
        "eval_count": 24,
        "eval_duration": 1_200_000_000,
        "prompt_eval_count": 8,
        "load_duration": 300_000_000,
    }
    with patch.object(server, "ollama_json", return_value=response):
        result = server.run_local_model_benchmark(server.QWEN3_2507_MODEL)
    assert result["model"] == server.QWEN3_2507_MODEL
    assert result["promptTokens"] == 8
    assert result["outputTokens"] == 24
    assert result["tokensPerSecond"] == 20.0
    assert result["status"] == "complete"
```

- [ ] **Step 3: テストが未実装で失敗することを確認する**

```bash
python3 scripts/test_server_helpers.py
```

期待結果: `model_benchmark_allowed` が未定義で失敗。

- [ ] **Step 4: 純粋関数と計測関数を実装する**

`model_benchmark_allowed(model: str, available_models: set[str]) -> bool` と
`run_local_model_benchmark(model: str) -> dict[str, object]` を追加する。

計測payload:

```python
{
    "model": model,
    "prompt": "日本語で一文だけ、準備できましたと答えてください。",
    "stream": False,
    "options": {
        "temperature": 0,
        "num_predict": 24,
    },
}
```

実装規則:

- `ollama_json("/api/generate", payload=payload, timeout=90)` を使う。
- `time.monotonic()` で全体時間を測る。
- `eval_duration` と `load_duration` はnanosecondから変換する。
- 0除算時の `tokensPerSecond` は0。
- promptや生成文をresponse、Memory、Knowledge、ファイルへ保存しない。
- 例外は既存JSON error形式へ変換し、stack traceをHTTP responseへ出さない。

- [ ] **Step 5: POST routeを追加する**

`do_POST()` に `/api/diagnostics/model-benchmark` を追加する。

処理順:

1. JSON bodyから文字列 `model` を読む。
2. Ollama `/api/tags` から取得済みモデル集合を作る。
3. `model_benchmark_allowed()` で検証する。
4. 拒否はHTTP 400と `benchmark_model_not_allowed`。
5. 合格時だけ `run_local_model_benchmark()` を1回呼ぶ。
6. 成功はHTTP 200。

- [ ] **Step 6: server testを合格させる**

```bash
python3 scripts/test_server_helpers.py
python3 -m py_compile server.py
```

期待結果: 終了コード0。

## Task 3: 診断UIへ理論値と実測値を分けて表示する

**Files:**

- Modify: `web/settings.js:60-205`
- Modify: `web/app.js:330-360`
- Modify: `web/app.js:8090-8110`
- Modify: `web/index.html`
- Modify: `web/i18n.js`
- Modify: `web/styles.css`
- Modify: `web/pwa.js`
- Modify: `web/sw.js`
- Test: `scripts/test-settings-helpers.js`
- Test: `scripts/test-pwa-assets.js`

- [ ] **Step 1: UI失敗テストを追加する**

`scripts/test-settings-helpers.js` の既存 `pcDiagnosticsEl` fixtureへ次を追加する。

```js
system: {
  os: "Windows",
  cpu: "Intel CPU",
  memoryGb: 16,
  isAppleSilicon: false,
  gpu: "NVIDIA GeForce RTX 4060",
  hasGpu: true,
  gpuInfo: {
    detected: true,
    name: "NVIDIA GeForce RTX 4060",
    vendor: "nvidia",
    vramGb: 8,
    vramConfidence: "high",
    unifiedMemory: false,
    source: "nvidia-smi",
  },
  ollamaVersion: "0.31.1",
  availableModels: [qwen2507, agenticCoder],
},
recommendation: {
  level: "heavy",
  label: "重い",
  basis: "theoretical",
  recommended: {
    standard: qwen2507,
    coding: agenticCoder,
    highPerformance: "",
  },
  warnings: [],
},
benchmark: null,
```

render後へ次を追加する。

```js
assert.match(pcDiagnosticsEl.innerHTML, /理論上の目安/);
assert.match(pcDiagnosticsEl.innerHTML, /NVIDIA GeForce RTX 4060/);
assert.match(pcDiagnosticsEl.innerHTML, /VRAM 8 GB/);
assert.match(pcDiagnosticsEl.innerHTML, /data-pc-benchmark-start/);
assert.doesNotMatch(pcDiagnosticsEl.innerHTML, /自動で切り替え/);
```

- [ ] **Step 2: UIテストが失敗することを確認する**

```bash
node scripts/test-settings-helpers.js
```

期待結果: `理論上の目安` またはベンチボタンがないため失敗。

- [ ] **Step 3: 表示を実装する**

`renderPcDiagnosticsPanel()` に次を追加する。

- `理論上の目安` ラベル。
- GPU名、VRAM、統合メモリ表示。
- `vramConfidence="estimated"` は `OSから取得した参考値` と表示し、確定値として推薦判定へ使わない。
- `短い速度テストを開始` ボタン。
- テスト前説明 `取得済みAIへ短い固定文を送り、このPC内だけで速度を測ります。モデルの取得・削除はしません。`
- 推薦standard modelが未取得またはauto-select不許可ならbuttonをdisabledにし、`速度テストには取得済みの標準AIが必要です` と表示する。
- 実行中、成功、拒否、Ollama未起動の状態。
- 結果としてモデル名、総時間、tokens/secを表示。

`state.pcBenchmark` の形:

```js
{
  status: "idle",
  result: null,
  error: "",
}
```

statusは `idle | running | complete | error` の4値だけとする。

- [ ] **Step 4: 明示操作handlerを実装する**

`web/app.js` のPC診断click handlerで `data-pc-benchmark-start` を処理する。

実装規則:

- 実行中はボタンをdisabledにする。
- 選択モデルは診断responseの `recommendation.recommended.standard` だけ。
- `POST /api/diagnostics/model-benchmark` へ送る。
- responseは `state.pcBenchmark` だけに保存する。
- localStorage、Memory、Knowledgeへ保存しない。
- 失敗してもモデル選択を変更しない。
- 同時実行を拒否する。

- [ ] **Step 5: 日本語と英語の文言を追加する**

追加key:

```text
settings.pcDiagnosticsTheoretical
settings.pcDiagnosticsBenchmarkStart
settings.pcDiagnosticsBenchmarkConsent
settings.pcDiagnosticsBenchmarkRunning
settings.pcDiagnosticsBenchmarkComplete
settings.pcDiagnosticsBenchmarkError
settings.pcDiagnosticsGpu
settings.pcDiagnosticsVram
settings.pcDiagnosticsUnifiedMemory
```

日本語literalを正とし、英語fallbackを同じcommitへ含める。

- [ ] **Step 6: UIテストと構文を合格させる**

```bash
node scripts/test-settings-helpers.js
node --check web/settings.js
node --check web/app.js
```

期待結果: 全て終了コード0。

- [ ] **Step 7: PWA資産版を更新する**

診断UIに関係する `settings.js`、`app.js`、`i18n.js`、`styles.css`、`pwa.js`、`web/sw.js` の参照を `0.8.231-pc-benchmark` に揃える。`scripts/test-pwa-assets.js` に `PC_DIAGNOSTICS_ASSET_VERSION` を追加し、更新対象だけをこの定数で検証する。models、asr、managementの既存版は変更しない。

```bash
node scripts/test-pwa-assets.js
```

期待結果: 終了コード0。

## Task 4: 回帰とブラウザーを確認する

- [ ] **Step 1: マスター計画のGlobal Verification Matrixを全実行する**

期待結果: 全コマンド終了コード0。

- [ ] **Step 2: Apple Siliconを確認する**

表示期待値:

- GPUはApple Silicon GPU。
- 統合メモリであることが表示される。
- VRAMと断定せず、共有メモリとして表示する。

- [ ] **Step 3: Windowsを確認する**

Windows実機または保存済みfixtureで次を確認する。

- NVIDIAまたはAMD名が表示される。
- VRAM値が表示される。
- PowerShellが使えない時は `GPU情報を取得できませんでした` となり、診断全体は失敗しない。

- [ ] **Step 4: ベンチ操作を確認する**

- ボタンを押す前はOllama generateを呼ばない。
- 取得済みQwen3 4Bで1回だけ測る。
- 未取得モデルIDの直接POSTはHTTP 400。
- テスト後も選択モデルは変わらない。
- promptと生成文が画面、Memory、Knowledgeに残らない。

- [ ] **Step 5: Tauri appで確認する**

`1280 × 820` と `960 × 640` で理論値、実測値、承認button、errorが表示できることを確認する。ベンチ中にapp windowを閉じた場合はowned requestとowned serverだけが終了し、Ollamaや別TOMOS processを停止しない。

## Gate 1

合格条件:

- GPU parser、許可判定、計測、UIの自動テストが合格。
- Apple Silicon、Windows、GPU未検出の3状態が確認済み。
- 実測は明示操作のみ。
- モデル取得、削除、外部送信、自動選択変更が0件。
- PC幅1440×900、Tauri app 1280×820 / 960×640、スマホ幅390×844が合格。

推奨commit message:

```text
feat: add consent-based local model benchmark
```

Directorがcommitと次Phaseを承認した後だけ、`2026-07-23-tomos-realtime-voice-input.md` へ進む。
