# TOMOS Desktop B2 API Session Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tauriが起動したTOMOS serverの状態変更APIを、起動ごとのsession token、Host、Origin、Content-Typeで保護する。

**Architecture:** Rustが32 byte tokenを生成してPython環境とWebView初期化scriptへ渡す。WebViewのfetch wrapperが同一originの状態変更requestへheaderを付け、serverはrouting前に共通guardを実行する。手動起動したブラウザー版はtoken環境変数がない時だけ現行動作を維持する。

**Tech Stack:** Rust、`getrandom` 0.3、Tauri WebView initialization script、Python `BaseHTTPRequestHandler`、JavaScript Fetch API

## Global Constraints

- Gate B1合格版を基準にする。
- tokenはfile、URL、localStorage、log、responseへ保存・表示しない。
- token不一致時は固定`403 {"ok":false,"error":"desktop_session_required"}`を返す。
- `/api/health`と静的assetはtokenなしで利用できる。
- browser fallbackはserverがdesktop sessionなしで起動した時だけ既存write動作を維持する。
- mobile sync serverの既存認証境界を変更しない。
- commitはDirectorの明示承認後だけ実行する。

---

### Task 1: Python request guardをテスト先行で追加

**Files:**
- Modify: `server.py`
- Modify: `scripts/test_server_helpers.py`

**Interfaces:**
- Produces:
  - `desktop_session_token() -> str`
  - `desktop_request_guard(method: str, path: str, headers: Mapping[str, str], expected_token: str) -> tuple[bool, str]`
  - `desktop_json_content_type_required(path: str) -> bool`

- [ ] **Step 1: token・Host・Origin・Content-Typeの失敗testを書く**

```python
def test_desktop_guard_rejects_missing_token():
    allowed, error = desktop_request_guard(
        "POST", "/api/context/memory/save",
        {"Host": "127.0.0.1:54876", "Origin": "http://127.0.0.1:54876", "Content-Type": "application/json"},
        expected_token="a" * 64,
    )
    assert not allowed
    assert error == "desktop_session_required"

def test_desktop_guard_accepts_matching_session():
    allowed, error = desktop_request_guard(
        "POST", "/api/chat",
        {
            "Host": "127.0.0.1:54876",
            "Origin": "http://127.0.0.1:54876",
            "Content-Type": "application/json; charset=utf-8",
            "X-TOMOS-Session": "a" * 64,
        },
        expected_token="a" * 64,
    )
    assert allowed
    assert error == ""
```

- [ ] **Step 2: REDを確認する**

Run: `python3 scripts/test_server_helpers.py`

Expected: `desktop_request_guard`未定義で失敗。

- [ ] **Step 3: guardを最小実装する**

`GEMMA_DESKTOP_SESSION_TOKEN`が空なら既存localhost動作を維持する。設定済みならPOSTをguard対象とし、`hmac.compare_digest`でtoken比較する。Hostは`127.0.0.1:54876`と`localhost:54876`、Originは同じ2 originだけを許可する。

JSON専用endpointは明示setで管理する。multipart upload、stream、file pickerへ誤ってJSONを強制しない。

- [ ] **Step 4: Handler routing前へguardを接続する**

`do_POST()`の最初でguardを実行し、失敗時は固定403を返してbodyを読まない。`log_message()`はtokenを含むheaderやqueryを出さない現行形式を維持する。

- [ ] **Step 5: GREENを確認する**

Run:

```bash
python3 scripts/test_server_helpers.py
python3 -m py_compile server.py
```

Expected: server helper全件合格。

---

### Task 2: Rust token生成とPython子プロセス伝達

**Files:**
- Modify: `src-tauri/Cargo.toml`
- Modify: `src-tauri/src/runtime.rs`
- Modify: `src-tauri/src/lib.rs`

**Interfaces:**
- Produces:
  - `generate_session_token() -> Result<String, RuntimeError>`
  - `RuntimeSupervisor::start(paths: &RuntimePaths, session_token: &str)`
  - 子process環境`GEMMA_DESKTOP_SESSION_TOKEN`

- [ ] **Step 1: token形式testを書く**

```rust
#[test]
fn generates_64_character_hex_session_token() {
    let token = generate_session_token().unwrap();
    assert_eq!(token.len(), 64);
    assert!(token.bytes().all(|byte| byte.is_ascii_hexdigit()));
}

#[test]
fn creates_a_new_token_for_each_launch() {
    assert_ne!(generate_session_token().unwrap(), generate_session_token().unwrap());
}
```

- [ ] **Step 2: REDを確認する**

Run: `cargo test --manifest-path src-tauri/Cargo.toml`

Expected: `generate_session_token`未定義でcompile失敗。

- [ ] **Step 3: `getrandom`依存とtoken生成を実装する**

```toml
getrandom = "0.3"
```

```rust
pub fn generate_session_token() -> Result<String, RuntimeError> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes).map_err(|_| RuntimeError::SessionToken)?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}
```

- [ ] **Step 4: Pythonへtokenを渡す**

`Command`へ`.env_clear()`を使わず、必要な現行環境を維持した上で`GEMMA_DESKTOP_SESSION_TOKEN`だけを明示設定する。tokenをDebug表示する型やerrorへ含めない。

- [ ] **Step 5: GREENを確認する**

Run: `cargo test --manifest-path src-tauri/Cargo.toml`

Expected: token testを含め全件合格。

---

### Task 3: WebView fetch wrapperを初期化scriptで注入

**Files:**
- Modify: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/session.rs`
- Modify: `scripts/test-desktop-shell-contract.py`

**Interfaces:**
- Produces: `session::initialization_script(token: &str) -> String`。

- [ ] **Step 1: script契約testを書く**

```rust
#[test]
fn initialization_script_adds_session_only_to_local_api_mutations() {
    let script = initialization_script(&"a".repeat(64));
    assert!(script.contains("X-TOMOS-Session"));
    assert!(script.contains("127.0.0.1:54876"));
    assert!(!script.contains("localStorage"));
    assert!(!script.contains("console."));
}
```

- [ ] **Step 2: REDを確認する**

Run: `cargo test --manifest-path src-tauri/Cargo.toml session::tests`

Expected: `session` module未定義で失敗。

- [ ] **Step 3: closure内fetch wrapperを実装する**

scriptは元の`window.fetch`を保持する。request URLが現在originの`/api/`で、methodがPOST/PUT/PATCH/DELETEの時だけheaderを追加する。tokenをwindow propertyへ公開しない。Request objectと文字列URLの両方を扱い、既存headerを保持する。

- [ ] **Step 4: main WebViewへ初期化scriptを設定する**

token生成後、Python起動と同じtokenからscriptを作り、`WebviewWindowBuilder`へ設定する。token生成失敗時はwindowを開かず固定日本語エラーへ落とす。

- [ ] **Step 5: GREENを確認する**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
python3 scripts/test-desktop-shell-contract.py
```

Expected: 全件合格、token literalを診断出力しない。

---

### Task 4: 実HTTP境界testとGate B2

**Files:**
- Create: `scripts/test_desktop_api_session.py`
- Modify: `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md`

**Interfaces:**
- Consumes: 同梱Python server、固定portではなくtest用空きport。
- Produces: tokenあり・なしのHTTP integration evidence。

- [ ] **Step 1: subprocess server integration testを書く**

testは一時data rootとランダムtokenでserverを起動し、次を実HTTPで確認する。

```text
GET /api/health                         -> 200または503、token不要
POST /api/chat tokenなし               -> 403
POST /api/chat 誤token                  -> 403
POST /api/chat 誤Host                   -> 403
POST /api/chat 誤Origin                 -> 403
POST /api/chat text/plain               -> 403
POST /api/chat 正token application/json -> guard通過後の通常response
```

通常responseはOllama成功を要求せず、`403 desktop_session_required`ではないことを確認する。

- [ ] **Step 2: testを実行する**

Run: `python3 scripts/test_desktop_api_session.py`

Expected: 全case合格、process終了後port解放。

- [ ] **Step 3: browser fallback regressionを実行する**

Run:

```bash
python3 scripts/test_server_helpers.py
node scripts/test-pwa-assets.js
node scripts/test-tts-helpers.js
```

Expected: desktop tokenなしの既存経路が全件合格。

- [ ] **Step 4: secret leak scanを行う**

app起動後のURL、log、localStorage key一覧、`/api/health` responseを確認し、64文字tokenが0件であることを確認する。tokenそのものをterminalへ出力しない検査helperを使う。

- [ ] **Step 5: Gate B2判定**

全test合格後だけマスター台帳のGate B2を`合格`へ更新し、Gate B3開始を許可する。
