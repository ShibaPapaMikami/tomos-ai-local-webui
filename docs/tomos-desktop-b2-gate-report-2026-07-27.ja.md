# TOMOS Desktop Gate B2 検証報告

## 判定

- Gate B2: **合格**
- 対象HEAD: `80294b9` を基準とする未コミットB2実装
- 検証日: 2026-07-27
- 対象: localhost API session保護

## 実装境界

- デスクトップ起動ごとに64文字のランダムなsession tokenを生成する。
- tokenはPython serverの環境変数とWebView初期化scriptだけへ渡す。
- mutation APIはHost、session token、Origin、JSON Content-Typeを検証する。
- token有効時はGETを含む全methodでHostを検証する。
- Pythonから直接またはproduction既定runner経由で起動する全子processではsession tokenだけを環境から除去する。
- browser版はtoken未設定時の既存経路を維持する。

## 修正後の自動検証

production既定runner経路の修正後に以下を再実行し、すべて成功した。

```bash
python3 scripts/test_server_helpers.py
python3 scripts/test_desktop_api_session.py
python3 scripts/test-desktop-shell-contract.py
node scripts/test-pwa-assets.js
node scripts/test-tts-helpers.js
cargo test --manifest-path src-tauri/Cargo.toml
git diff --check
```

- Python helperとHTTP結合testはlocalhost listenerを使うためsandbox外で実行した。
- Rust testは22件成功した。
- 不正Hostの機密GET、tokenなし・誤token・誤Origin・不正Content-Typeのmutationを固定403で拒否した。
- 正しいHostのhealth GETと正tokenのmutationはguardを通過した。
- `server.py` 内の直接記述20件とproduction既定runner経由5件が共通のtoken除去環境を使うことをAST testで確認した。
- 注入fake runnerでもtoken非継承と無関係な環境変数の維持を確認した。

## 修正後の実アプリ検証

- dirty sourceからrelease配布物とは別の一時appを生成し、ad-hoc署名して `/private/tmp` から起動した。
- `/Applications`、正式candidate、署名鍵、公証、本番環境は変更していない。
- app本体1process、同梱Python server 1process、`127.0.0.1:54876`だけの待受を確認した。
- `/api/health` は `200`、`ok=true`、`appVersion=0.8.233` を返した。
- tokenなしの `POST /api/chat` と不正Hostの `GET /api/context/memory/list` は固定403を返した。
- 正しいHostのhealth GETはtokenなしで200を返した。
- WebKit origin記録は `tauri://localhost` と `http://127.0.0.1` だけだった。
- LocalStorageは既存の `gemma4.*` 16 keyだけで、session token名、header名、64文字hex候補は0件だった。
- 直近system log 331,331 byteにsession token名、header名、64文字hex候補は0件だった。
- macOSの通常終了操作後、appと同梱Pythonが終了し、port 54876の解放を確認した。
- 起動後もbundle resource hash、ad-hoc署名、TOMOS resource内の`__pycache__`非生成を確認した。

## 安全上の記録

- session tokenの値は読み出しも表示もしていない。
- token漏えい検査はmarker名と64文字hex候補の件数だけを出力した。
- この検証はB2の実装Gateに限定し、正式配布、Developer ID署名、Apple公証、PKG installの承認ではない。

## 次工程

- Gate B3: app data、preview、承認付きcopy移行。
- B3開始前に本報告とB2差分をcommitし、Director承認を得る。
