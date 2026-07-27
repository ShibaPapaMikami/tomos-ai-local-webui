pub fn initialization_script(token: &str) -> String {
    let token_literal = format!("{token:?}");

    format!(
        r#"(() => {{
  const sessionToken = {token_literal};
  const tomosOrigin = "http://127.0.0.1:54876";
  const originalFetch = window.fetch;
  const mutationMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  window.fetch = (input, init) => {{
    const inputIsRequest = input instanceof Request;
    const requestUrl = inputIsRequest
      ? new URL(input.url, window.location.origin)
      : new URL(input, window.location.origin);
    const requestMethod = init?.method ?? (inputIsRequest ? input.method : "GET");
    const isLocalApi = window.location.origin === tomosOrigin
      && requestUrl.origin === window.location.origin
      && requestUrl.pathname.startsWith("/api/");

    if (!isLocalApi || !mutationMethods.has(requestMethod.toUpperCase())) {{
      return originalFetch.call(window, input, init);
    }}

    const request = inputIsRequest
      ? new Request(input, init)
      : new Request(requestUrl, init);
    const headers = new Headers(request.headers);
    headers.set("X-TOMOS-Session", sessionToken);
    return originalFetch.call(window, new Request(request, {{ headers }}));
  }};
}})();"#
    )
}

#[cfg(test)]
mod tests {
    use super::initialization_script;
    use std::process::Command;

    #[test]
    fn initialization_script_adds_session_only_to_local_api_mutations() {
        let script = initialization_script(&"a".repeat(64));

        assert!(script.contains("X-TOMOS-Session"));
        assert!(script.contains("127.0.0.1:54876"));
        assert!(script.contains("POST"));
        assert!(script.contains("PUT"));
        assert!(script.contains("PATCH"));
        assert!(script.contains("DELETE"));
        assert!(script.contains("new URL"));
        assert!(script.contains("input instanceof Request"));
        assert!(script.contains("new Headers"));
        assert!(script.contains("new Request(request, { headers })"));
        assert!(script.contains("requestUrl.origin === window.location.origin"));
        assert!(script.contains("requestUrl.pathname.startsWith(\"/api/\")"));
        assert!(script.contains("originalFetch.call(window, input, init)"));
        assert!(!script.contains("localStorage"));
        assert!(!script.contains("console."));
        assert!(!script.contains("window.TOMOS"));
    }

    #[test]
    fn initialization_script_preserves_non_mutating_and_external_fetches() {
        let script = initialization_script(&"a".repeat(64));
        let javascript_test = r#"
const vm = require("node:vm");
const script = process.argv[1];
const calls = [];

class Headers {
  constructor(init = {}) {
    this.values = new Map();
    if (init instanceof Headers) {
      for (const [key, value] of init.values) this.set(key, value);
    } else {
      for (const [key, value] of Object.entries(init)) this.set(key, value);
    }
  }
  set(key, value) { this.values.set(key.toLowerCase(), String(value)); }
  get(key) { return this.values.get(key.toLowerCase()) || null; }
}

class Request {
  constructor(input, init = {}) {
    if (input instanceof Request) {
      this.url = input.url;
      this.method = init.method || input.method;
      this.headers = new Headers(init.headers || input.headers);
    } else {
      this.url = String(input);
      this.method = init.method || "GET";
      this.headers = new Headers(init.headers);
    }
  }
}

const window = {
  location: { origin: "http://127.0.0.1:54876" },
  fetch(input, init) {
    calls.push({ input, init });
    return Promise.resolve();
  },
};
vm.runInNewContext(script, { window, Headers, Request, URL });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
function latest() {
  return calls[calls.length - 1];
}
function assertMutation(method, input) {
  window.fetch(input, { method, headers: { "X-Kept": method } });
  const request = latest().input;
  assert(request instanceof Request, method + " should create a guarded Request");
  assert(request.headers.get("x-tomos-session") === "a".repeat(64), method + " should carry session");
  assert(request.headers.get("x-kept") === method, method + " should keep headers");
}

assertMutation("POST", "/api/chat");
assertMutation("PUT", new Request("http://127.0.0.1:54876/api/settings", { method: "PUT" }));
assertMutation("PATCH", "/api/context/memory/save");
assertMutation("DELETE", "/api/context/memory/delete");

window.fetch("/api/chat", { method: "GET", headers: { "X-Kept": "get" } });
assert(typeof latest().input === "string", "GET must remain unwrapped");
assert(latest().init.headers["X-TOMOS-Session"] === undefined, "GET must not receive session");

window.fetch("https://example.test/api/chat", { method: "POST", headers: { "X-Kept": "external" } });
assert(typeof latest().input === "string", "external origin must remain unwrapped");
assert(latest().init.headers["X-TOMOS-Session"] === undefined, "external origin must not receive session");

window.fetch("/styles.css", { method: "POST", headers: { "X-Kept": "static" } });
assert(typeof latest().input === "string", "static path must remain unwrapped");
assert(latest().init.headers["X-TOMOS-Session"] === undefined, "static path must not receive session");
"#;

        let output = Command::new("node")
            .arg("-e")
            .arg(javascript_test)
            .arg(script)
            .output()
            .expect("Node.js is required for WebView fetch wrapper tests");

        assert!(
            output.status.success(),
            "WebView fetch wrapper behavior test failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    #[test]
    fn initialization_script_does_not_consume_non_target_request_bodies() {
        let script = initialization_script(&"a".repeat(64));
        let javascript_test = r#"
const vm = require("node:vm");
const script = process.argv[1];
let externalRequest;
let targetRequest;
let externalOriginalFetchUsedBody = false;
let targetOriginalFetchUsedBody = false;

const window = {
  location: { origin: "http://127.0.0.1:54876" },
  async fetch(input) {
    if (input === externalRequest) {
      if (input.bodyUsed) throw new Error("non-target request body was consumed before original fetch");
      externalOriginalFetchUsedBody = true;
      return input.text();
    }
    if (input === targetRequest) {
      throw new Error("target request was not guarded");
    }
    if (input.headers.get("x-tomos-session") !== "a".repeat(64)) {
      throw new Error("guarded target request is missing session header");
    }
    if (input.headers.get("x-kept") !== "target") {
      throw new Error("guarded target request lost its existing header");
    }
    if (input.bodyUsed) throw new Error("guarded target request body was consumed before original fetch");
    targetOriginalFetchUsedBody = true;
    return input.text();
  },
};
vm.runInNewContext(script, { window, Headers, Request, URL });

(async () => {
  externalRequest = new Request("https://example.test/api/chat", { method: "POST", body: "external body" });
  const externalBody = await window.fetch(externalRequest);
  if (externalBody !== "external body" || !externalOriginalFetchUsedBody || !externalRequest.bodyUsed) {
    throw new Error("non-target request body was not left for original fetch");
  }

  targetRequest = new Request("http://127.0.0.1:54876/api/chat", {
    method: "POST",
    body: "target body",
    headers: { "X-Kept": "target" },
  });
  const targetBody = await window.fetch(targetRequest);
  if (targetBody !== "target body" || !targetOriginalFetchUsedBody) {
    throw new Error("target request body was not preserved on guarded copy");
  }
})().catch((error) => {
  process.nextTick(() => { throw error; });
});
"#;

        let output = Command::new("node")
            .arg("-e")
            .arg(javascript_test)
            .arg(script)
            .output()
            .expect("Node.js is required for WebView fetch wrapper tests");

        assert!(
            output.status.success(),
            "WebView request body preservation test failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
}
