# macOS App Launcher 最終修正報告

## 対象

- review `c7b8bb1..6e554f1` の Critical / Important 5件のみを修正した。
- 公開、実署名、公証、PKGインストールは実行していない。

## 修正内容

1. Mac ZIPへ`server.py`のローカルPython依存と`packages/local_context_core`を同梱し、展開後の`/api/health`起動smokeを追加した。
2. `.app`起動時は`~/Library/Application Support/TOMOS AI`を可変データの保存先にし、旧`/Applications/Gemma4_12B`の`.gemma4-data`と人物写真を、保存先が未作成の場合だけコピーする。旧データは変更・削除しない。
3. `.app`生成時はMac ZIPを必ず現ソースから再生成する。
4. health JSONの`appVersion`が`0.8.220`の場合だけ既存サーバーを再利用する。別バージョン、起動ファイル欠落、起動失敗を別ダイアログにし、失敗時は自分が開始したPIDだけ終了する。
5. PKG生成はad-hoc Application署名を拒否し、`codesign --verify --deep --strict`とDeveloper ID Application authorityを確認してから`pkgbuild`する。

## テスト先行の確認

- 依存漏れ、ZIP再利用、旧サーバー再利用、初回移行、Application Support保存先、ad-hoc PKG拒否のテストを先に追加し、修正前の失敗を確認した。

## 検証結果

- `python3 scripts/test_macos_app_bundle.py` : PASS
- `python3 scripts/test_macos_app_launcher.py` : PASS
- `python3 scripts/test_tomos_app_data.py` : PASS
- `python3 scripts/test_mac_pkg_signing.py` : PASS
- `node scripts/test-pwa-assets.js` : PASS
- `python3 scripts/test-agent-reach-routing-smoke.py` : PASS
- `bash -n scripts/macos-app-launcher.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh` : PASS
- `python3 -m py_compile server.py` : PASS
- `git diff --check` : PASS

## 既存失敗

- `python3 scripts/test_server_helpers.py` は変更前からのOCR環境依存で失敗した。`.venv-ocr/bin/python`がなく、`sarashina_ocr_status()`が`needs_runner`を返す一方、テストは`needs_runner`を許容していない。本修正の対象外のため変更していない。
