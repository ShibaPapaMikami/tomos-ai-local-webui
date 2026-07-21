# macOS PKG署名・公証設計

## 目的

GitHub Releasesで配布するTOMOS AIのmacOS用PKGを、個人名義のDeveloper ID Installerで署名し、Apple公証済みの状態にする。Gatekeeperを回避する操作を利用者へ要求しない。

## 方針

- `scripts/make-mac-pkg.sh`は署名証明書を必須にし、証明書がない環境では未署名PKGを生成せず失敗する。
- 証明書は`TOMOS_MAC_INSTALLER_IDENTITY`で明示指定できる。未指定時はMacのキーチェーンからDeveloper ID Installerを1件だけ自動検出する。
- `scripts/notarize-mac-pkg.sh`が署名確認、Apple公証、staple、Gatekeeper検証を順番に行う。
- 公証認証はMacのキーチェーンに保存済みの`tomos-notary`を参照し、秘密鍵やAPIキーをリポジトリへ保存しない。
- GitHub Actions上に証明書がない場合は、未署名成果物を作らず失敗させる。macOS版は当面、署名用Macで作成してReleaseへ添付する。

## 失敗時

- 署名証明書が0件または複数件なら、証明書名の明示指定を促して停止する。
- 署名、公証、staple、Gatekeeper検証のいずれかが失敗したPKGは公開しない。
- Windows MSIには影響を与えない。

## 検証

- パッケージスクリプトの安全条件を自動テストする。
- `pkgutil --check-signature`で個人名義のDeveloper ID Installerを確認する。
- `xcrun notarytool submit --wait`がAcceptedになることを確認する。
- `xcrun stapler validate`と`spctl -a -vv -t install`が成功することを確認する。
