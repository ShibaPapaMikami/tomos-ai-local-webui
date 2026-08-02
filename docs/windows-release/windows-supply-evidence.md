# Windows供給の読取証跡

## 状態と境界

この文書は承認済みの読取証跡のみを記録する。D0 Gate承認ではなく、署名または公開を
許可しない。将来のlock/build用入力では必要なバイトを再検証しなければならず、そのバイトは
このリポジトリに保存していない。

V310のHEAD-only検証は、公式URL、x64アーキテクチャ、成果物名、サイズ、およびWebView2
EULAの到達可能性を再確認した。応答本文またはruntimeバイトは取得していない。以下で
既存のバイト読取と記すSHA-256は承認済みの既存証跡であり、新しいV310のバイト検証ではない。

状態値: `confirmed` = 承認済みの読取結果が利用可能、`unresolved` = 発行または読取の
事実が未取得、`blocked` = unresolvedの事実がconfirmedになるまで進めてはならない作業。

## Python組込みruntime

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| リリースページ | https://www.python.org/downloads/release/python-3146/ | confirmed | 公式URLはV310 HEAD-only検証で再確認。 |
| 取得元URL | https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip | confirmed | 公式URLはV310 HEAD-only検証で再確認。 |
| バージョン | `3.14.6` | confirmed | 承認済みの読取結果。 |
| 成果物 | `python-3.14.6-embed-amd64.zip` | confirmed | V310 HEAD-only検証で再確認。 |
| アーキテクチャ | `x64` | confirmed | V310 HEAD-only検証で再確認。 |
| サイズ | `12570832` bytes | confirmed | V310 HEAD-only検証で再確認。 |
| SHA-256 | `df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c` | confirmed | 承認済みの既存バイト読取ダイジェスト。lock/build用入力の作成時に再検証する。 |
| ライセンス | `PSF-2.0` | confirmed | 承認済みの読取結果。 |
| ライセンスURL | https://raw.githubusercontent.com/python/cpython/v3.14.6/LICENSE | confirmed | 承認済みの読取結果。 |
| ライセンスSHA-256 | `b0e25a78cffb43f4d92de8b61ccfa1f1f98ecbc22330b54b5251e7b6ba010231` | confirmed | 承認済みの既存バイト読取ダイジェスト。lock/build用入力の作成時に再検証する。 |
| リポジトリに保存したruntimeバイト | 未保存 | blocked | 将来のlock/build用入力より前に再検証が必要。 |

## Microsoft Edge WebView2 runtime

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| 製品ページ | https://developer.microsoft.com/en-us/microsoft-edge/webview2 | confirmed | 公式URLはV310 HEAD-only検証で再確認。 |
| 配布URL | https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/d06c217f-cef1-471d-a639-fad978ef4a40/MicrosoftEdgeWebView2RuntimeInstallerX64.exe | confirmed | 正確な公式配布URLはV310 HEAD-only検証で再確認。 |
| 候補バージョン | `150.0.4078.99` | confirmed | 承認済みの既存バイト読取候補。 |
| 成果物 | `MicrosoftEdgeWebView2RuntimeInstallerX64.exe` | confirmed | V310 HEAD-only検証で再確認。 |
| アーキテクチャ | `x64` | confirmed | V310 HEAD-only検証で再確認。 |
| サイズ | `203814608` bytes | confirmed | V310 HEAD-only検証で再確認。 |
| SHA-256 | `477c6a0cf79d29fdbfca3ea337fabe952a439b5da38d025cd2c59cc65a87947d` | confirmed | 承認済みの既存バイト読取ダイジェスト。lock/build用入力の作成時に再検証する。 |
| EULA URL | https://explore.microsoft.com/microsoft-edge/api/eula/webview2 | confirmed | 到達可能性はV310 HEAD-only検証で再確認。 |
| 正規化済み `evergreenHtml` UTF-8 SHA-256 | `ce6fa83e57c338256e5cabe9e1eea83076c271b0fdb253408213eeb08859d7b6` | confirmed | 承認済みの既存正規化バイト読取ダイジェスト。lock/build用入力の作成時に再検証する。 |
| リポジトリに保存したruntimeバイト | 未保存 | blocked | 将来のlock/build用入力より前に再検証が必要。 |

## Timestamp

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| 第一候補 | `DigiCert KeyLocker` | unresolved | 第一候補にすぎず、発行済み事業者の事実ではない。 |
| RFC 3161 URL | `http://timestamp.digicert.com` | confirmed | 承認済みの正確なエンドポイント。HTTP例外はこのraw exact URLだけに適用する。 |
| ダイジェスト | `sha256` | confirmed | 承認済みtimestampダイジェスト。 |
| Timestamp token、message imprint、およびTSA chain | 未読取 | blocked | 必須の署名検証はこの証跡記録の範囲外。 |

## 証明書

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| 事業者 | DigiCertは第一候補 | unresolved | 事業者の購入および発行は未完了。 |
| サブジェクト | 未発行 | unresolved | 発行および読取が必要。 |
| 発行者 | 未発行 | unresolved | 発行および読取が必要。 |
| SHA-256 fingerprint | 未発行 | unresolved | 発行および読取が必要。 |
| キー識別子 | 未発行 | unresolved | 発行および読取が必要。 |
| 有効期間 | 未発行 | unresolved | 発行および読取が必要。 |
| ストレージ読取 | 未発行 | unresolved | 発行および読取が必要。 |

## リリースgate

| 項目 | 状態 | 証跡メモ |
| --- | --- | --- |
| Windows supply lock生成の完了 | blocked | 証明書の発行/読取およびruntime-byte再検証が未完了。 |
| Task 2 | blocked | 再検証済み証跡からsupply lockを完成できるまで開始しない。 |
| 署名または公開 | blocked | この読取証跡は署名または公開を許可しない。 |
