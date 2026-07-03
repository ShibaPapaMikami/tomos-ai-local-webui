# character-core 更新運用

## 位置づけ

`character-core` はプラグインではなく、TOMOS AI の標準キャラクター基盤です。マイキャラ設定では「キャラクター安定化」としてON/OFFできます。

## ON/OFF

- ON: 名前、一人称、呼び方、口調ルールを追加し、キャラクターの崩れを抑えます。
- OFF: 従来のマイキャラPromptだけを使います。返答が硬い、重い、または相性が悪い時の退避用です。

初期値はONです。

## Dating側更新時の取り込み

1. Dating側で `@tomos-ai/character-core` を更新します。
2. Dating側で test / typecheck / build を通します。
3. TOMOS側の `web/tomos-character-core.js` を更新します。
4. TOMOS側で以下を実行します。

```bash
node scripts/test-tomos-character-core-browser.js
node scripts/test-character-core-adapter.js
node scripts/test-character-helpers.js
node scripts/test-pwa-assets.js
git diff --check
```

5. Safariで `http://127.0.0.1:54876/` を開き、通常チャットとマイキャラ反映を確認します。

## 将来

今は npm 依存を増やさず、ブラウザ用の静的実装をTOMOS側に置いています。
将来は生成スクリプトで Dating 側 package から `web/tomos-character-core.js` を作る形に移行します。
