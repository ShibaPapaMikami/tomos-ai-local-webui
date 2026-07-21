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
- `bash -n scripts/macos-app-launcher.sh scripts/make-release-archives.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh Gemma4_12B_Web.command` : PASS
- `PYTHONPYCACHEPREFIX=/tmp/tomos-pycache python3 -m py_compile server.py` : PASS
- `git diff --check` : PASS

## 最後Important修正

1. 起動監視プロセスは専用PGIDのリーダーとして残り、ownerファイルへPID・PGID・トークンを登録した後、親ランチャーのready handshakeを受けてから実際の起動コマンドを開始するようにした。
2. 所有判定から`ps`のcommand文字列比較を削除した。登録済みownerのPID・PGID・トークン・開始時刻だけを照合し、登録前に失敗した場合はrelease合図で監視プロセスを終了させるため、無関係プロセスへsignalを送らない。

### 最後Important検証

- テスト先行で、`nohup`がPythonへexec遷移し、owner登録を2秒遅延するfixtureを追加した。開始子プロセスのcleanupと無関係プロセス生存を確認した。
- `python3 scripts/test_macos_app_launcher.py` : PASS（20 tests）
- `python3 scripts/test_macos_app_bundle.py` : PASS（14 tests）
- `python3 scripts/test_tomos_app_data.py` : PASS
- `python3 scripts/test_mac_pkg_signing.py` : PASS
- `node scripts/test-pwa-assets.js` : PASS
- `python3 scripts/test-agent-reach-routing-smoke.py` : PASS
- `bash -n scripts/macos-app-launcher.sh scripts/make-release-archives.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh Gemma4_12B_Web.command` : PASS
- `PYTHONPYCACHEPREFIX=/tmp/tomos-pycache python3 -m py_compile server.py` : PASS
- `git diff --check` : PASS
- `bash -n scripts/macos-app-launcher.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh` : PASS
- `python3 -m py_compile server.py` : PASS
- `git diff --check` : PASS

## 既存失敗

- `python3 scripts/test_server_helpers.py` は変更前からのOCR環境依存で失敗した。`.venv-ocr/bin/python`がなく、`sarashina_ocr_status()`が`needs_runner`を返す一方、テストは`needs_runner`を許容していない。本修正の対象外のため変更していない。

## 最終再レビュー修正

1. ZIPは`dist`配下の一時ディレクトリへ両方を生成してから置換するようにした。片方の生成失敗時は既存ZIPを変更しない。
2. 接続できたHTTP応答は、404、不正JSON、別バージョンを含めてすべてポート競合として停止する。起動処理は開始しない。
3. 起動処理はPythonの`setsid()`で専用プロセスグループへ分離し、失敗時はそのグループだけへTERMを送る。子プロセスと無関係プロセスの生存を検証した。
4. 起動経路へ`PYTHONDONTWRITEBYTECODE=1`と`python3 -B`を追加し、配布ZIPから`__pycache__`、`.pyc`、`.pyo`を除外した。生成済み.appを実際に起動した後も署名検証が通ることを確認した。

### 再レビュー検証

- `python3 scripts/test_macos_app_bundle.py` : PASS
- `python3 scripts/test_macos_app_launcher.py` : PASS
- `python3 scripts/test_tomos_app_data.py` : PASS
- `python3 scripts/test_mac_pkg_signing.py` : PASS
- `node scripts/test-pwa-assets.js` : PASS
- `python3 scripts/test-agent-reach-routing-smoke.py` : PASS
- `bash -n scripts/macos-app-launcher.sh scripts/make-release-archives.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh Gemma4_12B_Web.command` : PASS
- `PYTHONPYCACHEPREFIX=/tmp/tomos-pycache python3 -m py_compile server.py` : PASS
- `git diff --check` : PASS

`python3 scripts/test_server_helpers.py` は前回と同じOCR仮想環境不足による既存失敗であり、今回の変更とは無関係。

## 残Important修正

1. 起動監視ラッパーを専用プロセスグループの所有者として残し、トークン、PID、PGID、開始時刻を照合してから失敗時にそのグループだけを終了するようにした。開始シェルが先に終了しても子プロセスをcleanupする。
2. healthの`curl`へconnect/max timeoutを指定し、healthが確認できない場合は短いTCP接続確認を行う。非HTTP・無応答のリスナーも競合として起動を停止する。

### 残Important検証

- `python3 scripts/test_macos_app_bundle.py` : PASS
- `python3 scripts/test_macos_app_launcher.py` : PASS（親先行終了、非HTTP、無応答を含む）
- `python3 scripts/test_tomos_app_data.py` : PASS
- `python3 scripts/test_mac_pkg_signing.py` : PASS
- `node scripts/test-pwa-assets.js` : PASS
- `python3 scripts/test-agent-reach-routing-smoke.py` : PASS
- 構文、`py_compile`、`git diff --check` : PASS

`python3 scripts/test_server_helpers.py` のOCR仮想環境不足による既存失敗は継続している。

## 追加残Important修正

1. 有効なランチャーロックの所有PIDと開始時刻が一致する間は、health未readyでもTCPポート占有を別サービス競合として扱わず、health成功まで待機する。ロック所有者が無効な場合のTCP競合停止は維持した。
2. 監視ラッパーはownerファイル登録を待たず、直接起動したPIDの開始時刻を直ちに記録する。owner未登録時でもPIDと開始時刻、専用PGIDを照合して自分のグループだけを終了し、専用PGID化前はラッパーPIDだけを終了する。

### 追加残Important検証

- `python3 scripts/test_macos_app_launcher.py` : PASS（有効ロック＋TCP確保＋health待機、owner未登録1秒遅延中の子プロセスcleanup、無関係プロセス生存を含む）
- `python3 scripts/test_macos_app_bundle.py` : PASS
- `python3 scripts/test_tomos_app_data.py` : PASS
- `python3 scripts/test_mac_pkg_signing.py` : PASS
- `node scripts/test-pwa-assets.js` : PASS
- `python3 scripts/test-agent-reach-routing-smoke.py` : PASS

## 残Important修正（親クラッシュ）

1. 起動ごとに親PIDとランダムトークンから固有のowner・release・readyファイル名を生成するようにした。旧監視プロセスは次回起動のreadyを参照できない。
2. ready受信前の監視プロセスは、親ランチャーPIDと開始時刻を定期照合する。親がSIGKILLまたはクラッシュで消えた場合、監視プロセスは実子を開始せず、固有の一時ファイルを削除して終了する。

### 残Important検証（親クラッシュ）

- テスト先行で、ready前に親ランチャーをSIGKILLして再起動するfixtureを追加した。旧監視プロセスと固有一時ファイルの消滅、起動コマンド1回、無関係プロセス生存を確認した。
- `python3 scripts/test_macos_app_launcher.py` : PASS（21 tests）
- `python3 scripts/test_macos_app_bundle.py` : PASS（14 tests）
- `python3 scripts/test_tomos_app_data.py` : PASS
- `python3 scripts/test_mac_pkg_signing.py` : PASS
- `node scripts/test-pwa-assets.js` : PASS
- `python3 scripts/test-agent-reach-routing-smoke.py` : PASS
- `bash -n scripts/macos-app-launcher.sh scripts/make-release-archives.sh scripts/make-mac-app.sh scripts/make-mac-pkg.sh scripts/notarize-mac-pkg.sh Gemma4_12B_Web.command` : PASS
- `PYTHONPYCACHEPREFIX=/tmp/tomos-pycache python3 -m py_compile server.py` : PASS
- `git diff --check` : PASS
