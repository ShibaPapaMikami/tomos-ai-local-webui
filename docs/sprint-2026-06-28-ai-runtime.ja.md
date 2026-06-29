# Sprint 2026-06-28: Local AI Runtime 接続

目的: 上位ロードマップを、直近で動く実装・制作タスクへ落とす。

対象:

- エンジニア
- 学習パック制作担当

## 今回の焦点

2. 教材パックのインポート、追加、有効化、モード選択、チャット反映を安定させる。
3. 学習セットと教材パックの責務を混ぜない。
4. 次の実装として、スマホPWA/PC取り込み、CodeGraph、キャラクター記憶へ進める準備をする。

## 現状確認


このフォルダーは `.gitignore` で除外されているため、社内情報やprivate教材をGitHubへ誤って入れにくい。

現在の構成:

```text
  pack.json
  README.md
  mvv.md
  value-writing-rules.md
  coordinator-communication-rules.md
  tone-guide.md
  avoid-phrases.md
  glossary.csv
  modes/
    slack-rewrite.md
    email-rewrite.md
    request-rewrite.md
    report-rewrite.md
    external-check.md
  examples/
    slack-examples.md
    email-examples.md
```

`pack.json` には5つのモードが定義済み。

- Slackを整える
- メールを整える
- 依頼文を整える
- 報告文を整える
- 外部送信前チェック

## 実施済み確認

- [x] `pack.json` が正しいJSONとして読める
- [x] `visibility: "private"` が維持されている
- [x] 5つのモードが定義されている
- [x] `modes/*.md` の参照先がすべて存在する
- [x] 各modeの本文が空ではない
- [x] 配信HTMLに「教材パック」「学習セット」「プラグイン」の設定メニューが含まれる
- [x] `node scripts/test-management-helpers.js` が通る
- [x] `node --check web/management.js` が通る
- [x] `node --check web/app.js` が通る
- [x] `python3 -m py_compile server.py` が通る

未確認:

- [ ] Safari上で設定メニューを開き、教材パックパネルを目視確認する
- [ ] インポート後に5モードがチャット入力欄の教材パック選択へ出ることを確認する

Safariの自動操作は、`Allow JavaScript from Apple Events` とアクセシビリティ権限の制約で自動実行できなかったため、手動確認として残す。

## エンジニア向けタスク

### Task 1: 教材パック読み込みの回帰確認

目的: private教材パックが既存インポート機能で問題なく扱えることを確認する。

確認項目:

- [ ] `pack.json` が正しいJSONとして読める
- [ ] `modes/*.md` がすべて存在する
- [ ] 各modeの本文が空ではない
- [ ] `visibility: "private"` が維持されている
- [ ] インポート後、教材パック一覧に表示される
- [ ] 追加後、チャット入力欄の教材パック選択に5モードが出る
- [ ] 複数モード選択時に、チャットのシステム指示へ統合される
- [ ] 教材パック本体はユーザー操作で書き換わらない
- [ ] `修正して学習` は学習セットへ保存される

推奨確認コマンド:

```sh
node scripts/test-management-helpers.js
node --check web/management.js
node --check web/app.js
python3 -m py_compile server.py
git diff --check
```

### Task 2: 教材パック利用UXの確認


確認項目:

- [ ] 「教材パック」パネルを開ける
- [ ] private教材であることが分かる表示がある
- [ ] チャット画面で `Slackを整える` などのモードを選べる
- [ ] モード未選択時は、通常チャットに過剰干渉しない

UI文言の注意:

- `教材パック` は維持する
- `プロンプト` や `system prompt` は一般ユーザー向けに出しすぎない
- `private` は「この端末のみ」「社外共有しない」という説明にする

### Task 3: 学習セットとの接続


仕様:

```text
= 基本ルール、MVV、トーン、モード

= 実際に使って出た修正例、好み、追加ルール
```

実装/確認:

- [ ] 保存先として通常の学習セットを選べる
- [ ] 教材パック本体には保存しない
- [ ] 学習ノート表示で、元質問、保存した正しい回答、元AI回答、元チャット名を読める

### Task 4: 次スプリントの技術準備

次スプリント候補:

- [ ] CodeGraphのフォルダー単位ON/OFF
- [ ] スマホPWAの単体保存
- [ ] PC QR取り込み
- [ ] キャラクター記憶の一覧/編集/削除
- [ ] モデル一覧の用途ラベル

このスプリントでは着手しすぎない。
まず教材パックの実利用導線を固める。

## 学習パック制作担当向けタスク

### Task 1: MVV本文の社内確認

`mvv.md` のMission/Vision/Valueを確認する。

- [ ] Missionが最新か
- [ ] Visionが最新か
- [ ] Valueが最新か
- [ ] 社外共有してよい範囲か
- [ ] 「評価（社内のみ）」に該当する内容が混ざっていないか

確認が必要な場合は、ファイル内に追記せず、別メモで確認事項として残す。

### Task 2: 例文の追加

`examples/slack-examples.md` と `examples/email-examples.md` を育てる。

追加条件:

- [ ] Slack例を最低3件
- [ ] メール例を最低3件
- [ ] Before/After/理由をセットにする
- [ ] 実文面を使う場合は匿名化する
- [ ] 個人名、会社名、金額、契約、未公開案件名、URLを入れない

おすすめ例:

- 進行確認
- 依頼
- 相談
- 報告
- お礼
- 謝罪
- 外部送信前チェック

### Task 3: モード別チェック

各modeを1回ずつ実文に近い匿名サンプルで試す。

- [ ] Slackを整える
- [ ] メールを整える
- [ ] 依頼文を整える
- [ ] 報告文を整える
- [ ] 外部送信前チェック

評価観点:

- [ ] Gugenkaらしいか
- [ ] 丁寧すぎて重くないか
- [ ] 冷たすぎないか
- [ ] 次の行動が分かるか
- [ ] 事実を勝手に追加していないか
- [ ] 社外秘や未確定情報を出していないか

### Task 4: 学習セットへ保存するもの

教材パック本体にすぐ反映せず、まず学習セットに保存する。

保存してよいもの:

- 「Gugenkaではこの言い方を好む」
- 「この場面では結論を先に出す」
- 「この表現は冷たく見えるので避ける」
- 「外部送信前は未確定情報を確認事項に分ける」

保存しないもの:

- 実名
- 会社名
- 契約内容
- 金額
- 未公開案件
- 個人情報
- 実Slack/実メールの未匿名化本文

## 完了条件

このスプリントの完了条件:

- [ ] 5つのモードがチャット画面で選べる
- [ ] 1つ以上のモードで実際にリライトできる
- [ ] `修正して学習` が学習セットに保存される
- [ ] 学習セットのノート表示で保存内容を読める
- [ ] Slack例3件、メール例3件が匿名化済みで入っている
- [ ] `node scripts/test-management-helpers.js` が通る

## やらないこと

- クラウド同期
- 外部API連携
- 教材パック本体への自動書き込み
- 実メール/実Slackの未匿名化保存
- CodeGraph解析結果の本格統合
- スマホ単体LLM
- PC操作AI
