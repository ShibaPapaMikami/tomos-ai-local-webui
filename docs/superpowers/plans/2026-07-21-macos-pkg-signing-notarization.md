# macOS PKG署名・公証 実装計画

1. 署名必須条件と公証手順を検証するテストを追加し、現状で失敗することを確認する。
2. `make-mac-pkg.sh`へDeveloper ID Installerの選択、署名、署名検証を追加する。
3. `notarize-mac-pkg.sh`を追加し、公証、staple、Gatekeeper検証を一つの手順にする。
4. 配布ドキュメントを署名・公証済み前提へ更新する。
5. テストとシェル構文確認後、現在版のPKGをローカルで署名・公証する。
6. 公開前に署名者、公証、Gatekeeper判定、Git差分を確認する。
