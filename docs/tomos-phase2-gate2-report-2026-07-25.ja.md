# TOMOS Phase 2 Gate 2報告

## 判定

`合格`

コード、回帰テスト、localhost安全境界、ブラウザー表示は合格した。TOMOSアプリ版ではマイク許可、実マイクの列挙、会話欄での録音開始・停止、停止3秒後まで遅延結果が追加されないことまで合格した。再診断により、当初の0%表示は入力メーター開始前の値であり、WebViewには環境音とシステム音が届くことを確認した。音を認識しているか分かる5段階インジケーターも追加し、無音、環境音、人の声で表示が変化することを確認した。2026-07-26の最終試験では、人の声で「話している内容を受け取っています。」へ遷移し、Whisper高速が入力欄へ文字起こしを1回だけ確定した。認識結果は発話内容と異なる「ご視聴ありがとうございました」だったため、精度改善は今後の課題として残す。3秒後も同じ文が重複追加されず、通常版TOMOSと入力設定も復旧した。Gate 2を`合格`とし、Phase 3は開始承認まで停止する。

## Gate 2結果

```text
[Phase 2 / Gate 2]
基準HEAD: 016c52d352b544c04b319418941a36330e990771
変更ファイル: ASR、server、i18n、PWA、テスト、計画・報告
依存追加: なし
VAD tests: 合格（無音、100ms短音、発話開始、300ms短無音、650ms発話終了、1回確定）
session tests: 合格（停止、cancel、古いsession、遅延SpeechRecognition、partial/final重複防止）
resident tests: 合格（localhost限定、redirect禁止、WAV multipart、CLI fallback 1回）
既存tests: 合格（desktop shell、Cargo、model、settings、ASR、management、PWA、server、study pack、context、knowledge）
Mac実機: 合格（WebViewへの人声音声入力、5段階表示、VAD確定、Whisper高速による入力欄反映）
PC幅: 合格（1440×900、1280×820、960×640）
スマホ幅: 合格（390×844）
既存3経路: 自動テスト合格（Nemotron、Whisper CLI、ブラウザーSpeechRecognition）、Whisper CLIは実人声も合格
保存・外部送信: 0件（音声永続保存なし、localhost以外なし、自動送信なし）
未完了: Gate 2必須項目なし。Whisper高速の日本語認識精度改善は将来課題
```

## 実装済み

- 発話前の音声を送らず、発話開始と650msの無音を検出して1回だけ確定する。
- 暫定文字と確定文字を統合し、停止後・完了後・古いsessionの結果を破棄する。
- 停止時に録音、マイクtrack、AudioContext、timer、途中・確定requestを終了する。
- 常駐WhisperはHTTPのlocalhost、127.0.0.1、::1だけを許可し、失敗時は既存CLIへ1回だけ戻る。
- VAD非対応時は録音開始・音声送信を行わず、安全に資源を解放する。

## 検証記録

- `python3 scripts/test-desktop-shell-contract.py`
- `cargo test --manifest-path src-tauri/Cargo.toml`
- JavaScript構文確認
- `node scripts/test-model-selection.js`
- `node scripts/test-settings-helpers.js`
- `node scripts/test-asr-helpers.js`
- `node scripts/test-management-helpers.js`
- `node scripts/test-pwa-assets.js`
- `python3 scripts/test_server_helpers.py`
- `python3 scripts/test_study_pack_manager.py`
- `python3 scripts/test_context_core.py`
- `python3 scripts/test_knowledge_layer.py`
- `python3 -m py_compile server.py`
- `git diff --check`
- ローカル配信した `0.8.232-asr-vad.3` のreadback
- 4画面幅で横スクロールなし、音声入力ボタン、状態表示領域、音声入力設定を確認
- Phase 2のTauriアプリbundleを起動し、macOSのマイク許可ダイアログに用途説明が表示されることを確認
- TCCログでbundle IDへのマイク許可 `authValue=2` を確認
- 設定画面の「マイクを確認」を開始し、`MacBook Proのマイク / live / unmuted / enabled / audio: running` を確認
- 入力レベルは環境音1%、日本語合成音声最大3%、強いシステム音最大37%で変化し、WKWebViewの音声取得が動作することを確認
- 会話欄のマイクボタンで「話しかけてください。」へ遷移し、停止後は通常のマイク表示へ戻ることを確認
- 停止時に「音声入力を停止しました。」が表示され、3秒後まで入力欄と会話へ遅延結果が追加されないことを確認
- 旧VAD閾値では日本語合成音声を発話として検出せず、会話欄は「話しかけてください。」のままだった
- 0%だった旧診断は入力メーター未開始時の表示であり、WebViewの無信号ではなかった
- 初回診断時のmacOS入力音量は27%。追加承認までは設定を変更せずに診断した
- 追加承認後、macOS入力音量を75%へ一時変更して内蔵マイクを再試験したが、1秒間隔8回の入力メーターはすべて0%だった
- 入力音量75%でも改善しなかったため、音量不足を原因候補から除外した。試験後は27%へ復元した
- TOMOS側のマイク増幅は診断後に1.0倍へ復元した
- 追加承認後、AVFoundationで `MacBook Proのマイク` を音声入力0番として5.30秒録音した。解析結果は平均-55.7dB、最大-32.9dBで、OS単体では音声信号を確認できた
- 一時音声ファイル `/tmp/tomos-v026-mic-check.wav` は解析直後に削除し、存在しないことを確認した
- 実測音声に合わせ、VADと部分文字起こしの閾値をRMS 0.003、peak 0.01へ調整する
- 閾値調整後、強いシステム音でVADが発話終了を検出し、録音を自動停止してASR要求を1回だけ実行した
- Nemotron経路はASRランナー未設定のため、設定不足を示す安全なエラー表示で終了した
- 日本語合成音声は調整後も発話として確定しなかったため、2026-07-25時点では人の声による最終確認が残っていた
- 会話欄へ5段階の入力インジケーターを追加し、無音時は「話しかけてください。」、入力レベル1では「音を受け取っています。」へ変化することをアプリ版で確認した
- テストbundleはworktree内に作成し、bundle IDを本番版と分離してadhoc署名した。Developer ID署名、公証、配布は行っていない
- 2026-07-26、人の声で状態文が「話している内容を受け取っています。」へ変化することを確認した
- Whisper高速で実人声を文字起こしし、入力欄へ「ご視聴ありがとうございました」が1回だけ追加された。発話内容とは異なるため、経路は合格、精度は改善課題と判定した
- 文字起こし確定から3秒後も入力欄は同じ1文のままで、遅延結果や重複追加がないことを確認した
- 試験中にウィンドウが一時的にアクセシビリティ取得不能になったが、アプリとserverのPIDは継続し、再度openすると同じ入力欄状態で復帰した。クラッシュレポートは生成されていない
- 試験後、通常版 `0.8.230`、server起動元、macOS入力音量27%、`gemma4.micGain=1`をreadbackした

自動テストはすべて合格。実機は録音開始、人声検出、VADによる確定、Whisper高速の入力欄反映、3秒後の重複防止まで合格した。`scripts/test_server_helpers.py` はlocalhost一時ポートを使うため権限付きで実行した。

## レビュー

- 最終初回レビュー: Critical 0、Important 2、Minor 1
- Important修正後の再レビュー: Critical 0、Important 0、Minor 1、`APPROVED`
- 残るMinor: resident/CLI経路を設定診断画面へ明示する情報が未追加。Gate 2必須条件ではなく、経路の動作と安全性には影響しない。

## 次の操作

Gate 2は合格。Phase 3の開始承認までは、TTS、依存追加、モデル取得、外部音声API、配布作業へ進まない。
