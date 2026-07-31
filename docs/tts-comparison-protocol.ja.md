# TOMOS 音声エンジン比較手順

## 目的

VibeVoice RealtimeとQwen3-TTSを、同じ端末・同じ文章・同じTOMOS worker契約で比較する。Phase 3では記録様式だけを固定し、実エンジンやモデルは取得しない。

## 固定する10文

1. こんにちは。今日の予定を一緒に確認しましょう。
2. 午後三時から、開発チームとの打ち合わせがあります。
3. 資料の二ページ目に、重要な注意事項があります。
4. TOMOSは、このパソコンの中で安全に動作します。
5. 新潟県の明日の天気を調べてください。
6. GitHubの変更内容を、初心者にも分かるように説明します。
7. 一、二、三と数えてから、ゆっくり深呼吸してください。
8. 英語の「local artificial intelligence」を日本語で説明します。
9. 読み上げを停止したら、すぐに音が止まることを確認します。
10. ご利用ありがとうございました。またいつでも話しかけてください。

## 測定条件

- 順序: VibeVoice、Qwen3-TTS 0.6B、Qwen3-TTS 1.7B。別日に逆順でも測る。
- 各文章を3回測り、初回と再実行を分けて記録する。
- OS、CPU、RAM、GPU、VRAM、電源状態、TOMOS commitを記録する。
- LLM同時実行はQwen3 4Bへ固定promptを送り、TTSなしのtokens/secを基準にする。
- 音声、文章、測定結果はlocal-onlyとし、MemoryやKnowledgeへ保存しない。

## 評価項目

- 最初の音声までの時間（ms）
- 全体生成時間（ms）
- real-time factor
- peak RAM / peak VRAM
- LLM同時実行時のtokens/sec低下率
- 日本語の読み間違い数
- 自然さ（1から5）
- 停止から無音までの時間（ms）
- Windows CPUのみ、Windows GPU、Apple Siliconの成否

## 合格基準

標準音声候補:

- 最初の音声まで1500ms以下
- 停止から無音まで300ms以下
- 10文中の読み間違い2件以下
- LLM同時実行時のtokens/sec低下率40%以下
- Windowsで外部APIなしに動作

オリジナル音声候補:

- 最初の音声まで2500ms以下
- 停止から無音まで300ms以下
- 10文中の読み間違い2件以下
- 許諾のない音声を使わない

## 実エンジン導入前Gate

以下がすべて埋まり、依存追加とモデル取得がDirector承認されるまでfixture以外を実行しない。

```text
取得元:
commitまたはrelease:
license:
model license:
download size:
追加依存:
対応OS:
外部通信:
削除方法:
```
