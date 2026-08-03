# Windows供給の読取証跡

## 状態と境界

この文書は承認済みの読取証跡のみを記録する。D0 Gate承認ではなく、署名または公開を
許可しない。将来のlock/build用入力では必要なバイトを再検証しなければならず、そのバイトは
このリポジトリに保存していない。

V314では承認済みのHTTPS再取得とSHA-256再計算を行った。Python embedded ZIP、CPython
LICENSE、WebView2 installer、およびWebView2 EULA応答を一時領域だけに取得して照合し、
リポジトリには保存していない。ZIPとEXEは展開、実行、またはインストールしていない。
将来のlock/buildでは、その時点で取得したバイトをlockのsize/SHA-256と再照合しなければならない。

V320では、V314で確認済みのWebView2外装installerを実行せず、LZMA resourceを一時領域で
静的展開し、BCJ2復号後のtarを構造解析した。解析物は一時領域に残っているが、リポジトリには
保存していない。以下の内包Runtime版確認は静的な版同一性の証拠であり、Windows実機install、
Windows trust policy、失効確認、timestamp trustを確認したものではない。

状態値: `confirmed` = 承認済みの読取結果が利用可能、`unresolved` = 発行または読取の
事実が未取得、`blocked` = unresolvedの事実がconfirmedになるまで進めてはならない作業。

## Python組込みruntime

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| リリースページ | https://www.python.org/downloads/release/python-3146/ | confirmed | 承認済みの公式リリースページ。 |
| 取得元URL | https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip | confirmed | V314でHTTPS再取得した公式URL。 |
| バージョン | `3.14.6` | confirmed | 承認済みの読取結果。 |
| 成果物 | `python-3.14.6-embed-amd64.zip` | confirmed | V314でHTTPS再取得した。 |
| アーキテクチャ | `x64` | confirmed | 承認済みのx64成果物。 |
| サイズ | `12570832` bytes | confirmed | V314で再取得したバイト数。 |
| SHA-256 | `df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c` | confirmed | V314で再計算し、期待値と一致。 |
| ライセンス | `PSF-2.0` | confirmed | 承認済みの読取結果。 |
| ライセンスURL | https://raw.githubusercontent.com/python/cpython/v3.14.6/LICENSE | confirmed | V314でHTTPS再取得した公式URL。 |
| ライセンスサイズ | `13804` bytes | confirmed | V314で再取得したバイト数。 |
| ライセンスSHA-256 | `b0e25a78cffb43f4d92de8b61ccfa1f1f98ecbc22330b54b5251e7b6ba010231` | confirmed | V314で再計算し、期待値と一致。 |
| リポジトリに保存したruntimeバイト | 未保存 | confirmed | V314の再取得物は一時領域だけにあり、リポジトリには保存していない。 |

## Microsoft Edge WebView2 runtime

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| 製品ページ | https://developer.microsoft.com/en-us/microsoft-edge/webview2 | confirmed | 承認済みの公式製品ページ。 |
| 配布URL | https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/d06c217f-cef1-471d-a639-fad978ef4a40/MicrosoftEdgeWebView2RuntimeInstallerX64.exe | confirmed | V314でHTTPS再取得した正確な公式配布URL。 |
| Runtimeバージョン | `150.0.4078.99` | confirmed | V320でLZMA resourceを一時領域に静的展開し、BCJ2復号後のtarを構造解析して確認。`OfflineManifest.gup`のWebView2 entry、内部payload PEの実測値、固定・文字列VERSIONINFOが一致。 |
| 外装installer VERSIONINFO | `1.3.251.5` | confirmed | V314で最上位EXEのRT_VERSIONから静的に読取。内包Runtimeのバージョンではなく、lock versionには使用しない。 |
| 成果物 | `MicrosoftEdgeWebView2RuntimeInstallerX64.exe` | confirmed | V314でHTTPS再取得した。 |
| アーキテクチャ | `x64` | confirmed | 成果物名および承認済みのx64配布URL。 |
| サイズ | `203814608` bytes | confirmed | V314で再取得したバイト数。 |
| SHA-256 | `477c6a0cf79d29fdbfca3ea337fabe952a439b5da38d025cd2c59cc65a87947d` | confirmed | V314で再計算し、期待値と一致。 |
| EULA raw応答URL | https://explore.microsoft.com/microsoft-edge/api/eula/webview2 | confirmed | V314でHTTPS再取得した公式JSON応答URL。 |
| EULA JSONサイズ | `24429` bytes | confirmed | V314で再取得したJSON応答のバイト数。 |
| EULA JSON SHA-256 | `e15b53f476b66f8335c18436998256dc9862b210242a8e4c7f7e14d2de53591d` | confirmed | V314で再計算したraw JSON応答の取得証跡。lock用SHA-256ではない。 |
| lock用 `license_name` | `MICROSOFT SOFTWARE LICENSE TERMS — MICROSOFT EDGE WEBVIEW2 RUNTIME` | confirmed | V314で確認した`evergreenHtml`の見出し。 |
| lock用 `license_url` | https://explore.microsoft.com/microsoft-edge/api/eula/webview2 | confirmed | `license_name`と`license_sha256`の取得元となる公式JSON応答URL。 |
| 正規化済み `evergreenHtml` UTF-8サイズ | `21639` bytes | confirmed | V314で追加改行なしに抽出したUTF-8バイト数。 |
| lock用 `license_sha256` | `ce6fa83e57c338256e5cabe9e1eea83076c271b0fdb253408213eeb08859d7b6` | confirmed | 追加改行なしUTF-8の正規化済み`evergreenHtml`をlock採用値として固定。V314で再計算し、期待値と一致。 |
| リポジトリに保存したruntimeバイト | 未保存 | confirmed | V314の再取得物は一時領域だけにあり、リポジトリには保存していない。 |

### V320 内包payloadの静的照合

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| 解析境界 | LZMA resourceを一時領域で静的展開し、BCJ2復号後のtarを構造解析 | confirmed | 入力EXE、展開物、内部PEは実行・installしていない。 |
| WebView2 app ID | `{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` | confirmed | `OfflineManifest.gup`をXML構造として解析したWebView2 entry。 |
| manifest version | `150.0.4078.99` | confirmed | WebView2 entryのmanifest version。 |
| manifest package name | `MicrosoftEdgeWebview_X64_150.0.4078.99.exe` | confirmed | WebView2 entryのpackage name。 |
| manifest package size | `197845840` bytes | confirmed | WebView2 entryのpackage size。 |
| manifest package SHA-256 | `2d8f81e59e311a6dd77e0f79ae391120504475fa956038f1e1e35c3ada61848d` | confirmed | WebView2 entryのpackage SHA-256。 |
| 内部payload PE size/SHA-256 | `197845840` bytes / `2d8f81e59e311a6dd77e0f79ae391120504475fa956038f1e1e35c3ada61848d` | confirmed | 静的抽出した内部payload PEの実測値がmanifestと一致。 |
| 内部payload PE VERSIONINFO | 固定・文字列ともに`150.0.4078.99` | confirmed | `VS_FIXEDFILEINFO`および`StringFileInfo`のFileVersion/ProductVersionがすべて一致。 |
| 内部payload PE Authenticode digest | 記録内digestと静的再計算値が一致 | confirmed | 版同一性を補強する静的証拠。Windows trust policy、失効、timestampの検証済みを意味しない。 |
| Windows実機install、Windows trust policy、失効、timestamp trust | 未確認 | unresolved | 本証跡の静的解析対象外。 |
| 一時解析物 | 未削除、リポジトリ未保存 | confirmed | 一時領域の解析物は削除しておらず、リポジトリにも保存していない。 |

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
| runtime-byte再検証 | confirmed | V314でPython embedded ZIPおよびWebView2 installerの再取得、サイズ・SHA-256再計算を完了。 |
| WebView2内包Runtime version確認 | confirmed | V320静的構造解析で内包Runtime版`150.0.4078.99`を確認。外装installer VERSIONINFO `1.3.251.5`をlock versionに使用してはならない。 |
| Windows supply lock生成の完了 | blocked | 証明書の発行/読取が完了し、lockを作成できるまで生成しない。 |
| Task 2 | blocked | 証明書の発行/読取が完了し、supply lockを完成できるまで開始しない。 |
| 署名または公開 | blocked | この読取証跡は署名または公開を許可しない。 |
