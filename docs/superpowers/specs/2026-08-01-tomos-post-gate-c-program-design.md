# TOMOS Gate C後 統合開発プログラム設計

**日付:** 2026-08-01

**Director:** Codex

**設計基準:** `origin/main@6df62c09cb64044ed76480e417706ca2167a72ae`

## 1. 目的

Gate Cを通過したTOMOSを、初心者が安全に導入できるデスクトップアプリへ仕上げながら、次の機能を破綻なく追加する。

1. Mac / Windows配布の再現性とサポート導線
2. Markdown Skill Manager
3. 低遅延音声engine比較
4. PCに合うモデル比較
5. Company Memory、P2P、VRMの将来拡張

ユーザーの連絡先はDirectorに一本化する。各担当はDirectorから指示を受け、結果をDirectorへ返す。担当者同士の判断差はDirectorが正本、Gate、テスト結果を基準に解消する。

## 2. 今とこれから

| 領域 | 今 | これから | 完了を判断するGate |
| --- | --- | --- | --- |
| 正本 | リモート`main`はPR #5、#6統合済み。手元`main`は大きく分岐し既存変更がある | `origin/main`の固定commitから工程ごとの専用worktreeを作る | R0 |
| Macアプリ | v0.8.233は署名・公証・実機上書きまで合格 | 現在の正本と同じsourceから新しい版を再生成し、第三者の新規導入まで確認 | M0〜M2 |
| Windowsアプリ | MSIの表示名はTOMOS。旧ランチャー方式と静的テストが中心 | Tauri専用window、Windows用runtime、署名MSI、更新・削除・再導入を実機確認 | D0〜D3 |
| 初心者導入 | Macの旧ZIP案内とPKG方針が混在。安全な診断コピー画面がない | OS別1ページ、初回4段階、復旧手順、安全な診断情報を統一 | U0〜U2 |
| Skill | 詳細計画はあるが製品実装は未開始 | Markdown正本、固定評価、手動review、承認時だけ昇格 | Gate 4 |
| 音声出力 | 共通TTS境界とfixtureまで合格 | VibeVoice / Qwen3-TTSを隔離環境で比較。採用は別Gate | V0 / V1 |
| モデル | Qwen3標準、PC診断と承認付き実測まで合格 | 承認したartifactだけ同一条件で比較。自動取得・削除はしない | E0 / E1 |
| Company Memory | 個人向けLocal Context Coreが正本 | company scope、所有者、可視範囲、根拠、期限、忘却を別設計 | CM0 / CM1 |
| P2P | 未実装 | 架空fixtureの転送ラボから始め、会社データは初期deny | P2P0 / P2P1 |
| VRM | 未実装 | 初期OFFの表示専用shellから始め、合格済みTTSだけ後で接続 | VRM0 / VRM1 |

## 3. 正本と作業場所

### 3.1 正本

- 開始基準は`origin/main@6df62c09cb64044ed76480e417706ca2167a72ae`。
- 手元の既存`main`は既存変更を含むため、後続実装の開始点にしない。
- 旧`phase1-pc-diagnostics` worktreeは統合済みfeature branchの監査用として保持し、再利用しない。
- 各工程は正本から専用branchと専用worktreeを作成する。
- 工程開始時に`HEAD`、版番号、`git status --short --branch`を記録する。

### 3.2 計画の正本

| 対象 | 正本 |
| --- | --- |
| 全体順序とGate状態 | `docs/superpowers/plans/2026-07-23-tomos-evolution-master.md` |
| Skill Manager詳細 | `docs/superpowers/plans/2026-07-23-tomos-markdown-skill-manager.md` |
| 音声比較詳細 | `docs/superpowers/plans/2026-07-23-tomos-voice-engine-evaluation-lab.md` |
| モデル比較詳細 | `docs/superpowers/plans/2026-07-23-tomos-model-evaluation-lab.md` |
| 本設計 | Gate C後の実行順、担当、並行条件、配布・サポートGate |

既存の詳細計画と本設計が矛盾する場合は実装を止め、Directorが先に文書を整合させる。

### 3.3 今回変更する工程順

既存マスターはGate 4を先に進める順序になっている。本設計では、初心者へ安全に配布できる版を先に確立するため、Gate C直後にStage R / Uを置き、Gate 4をその後に変更する。

この変更はGate C合格を取り消さず、Skill、Voice、Modelの合格条件も変えない。設計承認後に作る実装計画の最初のTaskでマスター台帳とPhase Orderを本設計に合わせる。文書の整合が完了するまでは製品コードの次工程を開始しない。

## 4. チーム運営

| 担当 | 所有する成果 | 触らない範囲 |
| --- | --- | --- |
| Director | 正本、優先順位、Gate判定、ユーザー報告、merge順 | 承認なしの署名・公証・公開・依存追加 |
| エンジニア2 | Mac/Windows成果物、CI、署名検証、実機配布試験、rollback | Skill/Memory/Voiceの製品仕様 |
| ユーザー対応 | 初回導線、OS別ガイド、第三者試験、診断情報、問い合わせ手順 | 秘密情報、会話本文、ユーザーファイルの収集 |
| 追加機能担当 | Skill、Voice、Model、Company Memory、P2P、VRMの境界とテスト | 配布工程、未承認artifact取得、外部送信 |

### 4.1 報告経路

```text
ユーザー
  ↕
Director
  ├─ エンジニア2
  ├─ ユーザー対応
  └─ 追加機能担当
```

- ユーザーへの確認はDirectorがまとめる。
- 担当者は「確認済み」「未確認」「次のGate」「必要な承認」を分けて報告する。
- 実装担当は自分のworktree以外を変更しない。
- shared fileの所有者はDirectorがTask開始時に一人だけ指定する。

## 5. 統合ロードマップ

### Stage R: 正本・配布・サポート基盤

#### Gate R0: 正本固定

合格条件:

- `origin/main`の固定commitからclean worktreeを作成。
- version、commit、成果物の対応規則を明文化。
- release manifestに版、tag対象commit、tree SHA、clean状態、CI run、toolchain、runtimeのSHA・license、成果物名・size・SHA、署名者、timestamp、Mac公証IDを記録。
- Mac/Windows/Skillの対象ファイル所有者を確定。
- baseline testの実行条件を記録。
- fresh worktreeの`cargo test`に必要な生成済みmacOS runtimeがない場合、コード不良と混同せず、準備工程として扱う。
- マスター台帳とPhase Orderを本設計に合わせたdoc-only変更が完了。

#### 共通rollback contract

配布実装を始める前に、次の3種類を分けて固定する。

| 種類 | 戻す対象 | 必須条件 |
| --- | --- | --- |
| アプリ版rollback | PKG/MSIと実行ファイル | 直前の署名済み版が存在する場合だけ保持。旧版が現在のデータschemaを開けるか事前確認 |
| データ移行rollback | app dataの移行結果 | 移行前snapshotを1世代保持し、復元後の件数とhashを確認 |
| 設定取込rollback | 承認コピーした設定 | transfer manifestを保持し、コピー前の値へ戻せる |

- schema非互換がある版へ直接戻さない。先に対応するデータsnapshotを復元する。
- rollback前に現在のapp dataを別snapshotとして保全する。
- アンインストールはapp dataを削除せず、旧版installerを入れ直す順序をOS別に固定する。
- 自動削除は行わない。snapshot削除は対象、容量、復旧不能になる範囲を示して別承認を得る。

#### Gate M0: Mac公開source整合

現v0.8.233は署名・公証・実機確認済みだが、記録された製品source commitと現在の正本treeが一致しない。そのため現物PKGを現在の`main`由来として公開しない。

合格条件:

- 新版候補は原則`v0.8.234`以降。
- 選定したrelease commitからclean build。
- 版番号、source commit、PKG、SHA-256が一意に対応。
- 署名・公証操作を始める前にDirectorがユーザー承認を得る。

#### Gate M1: Mac再生成検証

- 自動テスト、Developer ID署名、Notary Accepted、stapler、Gatekeeperが合格。
- 新規導入と上書き導入で専用windowが起動。
- 既存チャット、Memory、Knowledge、教材、設定を削除しない。
- 不合格成果物は`dist/rejected/`へ隔離し、公開しない。

#### Gate M2: Mac第三者試験

- 開発者以外の学生役、教員役が配布URLだけで最初の質問まで完了。
- Macで学生役1名、教員役1名の試験記録を残す。
- Apple Siliconの対応最小macOSと現行macOSで、新規、更新、Ollamaなしを確認。
- Gatekeeper回避、ターミナル操作、Pythonの手動準備を要求しない。
- Ollama未導入・停止・通信切断・容量不足から安全に再試行できる。
- Mac単独のpreview公開は別承認とし、固有のprerelease版・tagを使う。非公開配布の場合も正式版と異なる成果物名にする。
- 公開済みtagの差し替えと、同じ版番号でのartifact交換を禁止する。
- 公開後はasset、tag、SHA、署名、公証を再取得してreadbackする。

#### Gate D0: Windows設計

- code-signing証明書、timestamp方式、秘密情報の扱いを固定。
- Windows Python runtimeの取得元、ライセンス、SHAを固定。
- WebView2方針、install先、ユーザーデータ保存先を固定。
- stable UpgradeCode、版ごとのProductCode、旧MSIからの更新、rollbackを固定。
- 直前の署名済みWindows版が存在するか確認する。存在しない初回版では「旧版へ戻せる」と表示せず、同版再導入とデータsnapshot復元だけを合格対象にする。
- 証明書・依存・外部取得は実行前に個別承認を得る。

#### Gate D1: Windows署名CI

- x64 Windows用runtimeとallowlist済み資源だけを同梱。
- ブラウザーではなくTauri専用windowを起動。
- exe/dllを先に署名し、最後にMSIを署名。
- CIで版整合、テスト、署名者、timestamp、SHAを検証。
- 未署名成果物を公開候補へ出さない。

#### Gate D2: Windows実機

- Windows 11実機で新規、更新、削除、再導入を確認。
- Ollama/Python/WebView2の有無、二重起動、ポート競合を確認。
- 終了時にTOMOSが所有するprocessだけを停止。
- アンインストールでモデル、Memory、Knowledge、教材、設定、チャットを削除しない。
- 再導入で既存データを再利用できる。
- 直前の署名済み版が存在し、データschemaに互換性がある場合だけ、旧版へ戻す試験を合格条件に加える。

#### Gate D3: Windows第三者試験

- Windowsで学生役1名、教員役1名が配布URLだけで最初の質問まで完了。
- 対応最小OSと現行OSで、新規、更新、依存なし、障害復旧を確認。
- app版、データ移行、設定取込の3種類のrollbackを実証。
- 初回署名版で旧署名版がない場合、app版rollbackは対象外と記録し、同版再導入、データ移行rollback、設定取込rollbackを実証。
- 次版以降は、schema互換を確認した直前の署名済み版へのapp版rollbackも実証。
- Windows単独のpreview公開は別承認とし、固有のprerelease版・tagを使う。公開済みtagの差し替えと同版artifact交換を禁止する。

#### Gate REL0: 正式Release候補

- Mac PKGとWindows MSIは同じtag、同じ版、追跡可能なsource commitから作成。
- Windows実装後の最終release commitからMac PKGも再生成し、Gate M1とM2を再通過する。
- 最終PKG/MSIのSHAを固定してから両OSの第三者smokeを行い、試験済みSHAと公開SHAを完全一致させる。再buildした場合は該当OSの第三者smokeをやり直す。
- 初心者向けReleaseには承認済みPKG/MSIと検証用SHAだけを案内。
- 旧Releaseはrollback用に保持。
- 公開操作は必ず別承認。
- 公開後はGitHubからPKG/MSIを再取得し、asset一覧、tag commit、各SHAをrelease manifestと照合する。
- 再取得物でMacの署名・公証・stapler・Gatekeeperと、WindowsのAuthenticode署名者・timestampを再検証する。

### Stage U: 初心者導入とサポート

Stage UはStage Rと並行して設計・文書化できる。製品UIのshared fileを変更する実装はDirectorのmerge順に従う。

#### Gate U0: 文書の一本化

- `README.ja.md`、学生向けガイド、Release案内から旧Mac ZIP中心の矛盾を除く。
- MacはPKG、Windowsは署名済みMSIを初心者向け正規導線とする。
- 対応OS、CPU、空き容量、通信量、Ollama、更新、復旧をOS別1ページにまとめる。
- GitHubのSource codeではなく、正確なPKG/MSIファイル名を案内する。

#### Gate U1: 初回4段階

```text
PCを確認
  → Ollamaを確認
  → 標準AIを取得
  → 試しに質問
```

- 不足時は理由、公式導入先、再試行を同じ画面に表示。
- Ollama未導入・停止でもアプリの案内画面を10秒以内に表示し、公式導入、再診断、終了を操作できる。
- Ollama確認は画面表示を止めず、backgroundでtimeout可能にする。
- Python同梱版では、利用者にPython手動操作を要求しない。
- 旧データ検出時は内容確認、承認コピー、元に戻すを案内。

#### Gate U2: 安全な診断

収集する:

- TOMOS版、source commit、OS、CPU、メモリ
- installer種別、Ollama/Python版、モデル取得状態
- エラーコード、ポート競合、発生時刻

収集しない:

- 会話本文、ファイル名、ユーザー名、保存先の全文
- 環境変数、token、Cookie、APIキー

合格条件:

- 画面から安全な診断情報をコピーできる。
- main windowが起動できない場合も、軽量な起動失敗画面またはOS別のローカル診断ファイルから同じ情報を取得できる。
- 診断生成時にユーザー名、絶対path、会話本文、環境変数、秘密情報を自動除外する。
- Mac/Windowsのclean install、更新、削除・再導入、復旧が第三者試験に合格。
- データの1世代rollbackと、対象版が存在する場合のアプリ版rollbackを別々に実証。
- 初回Windows署名版はapp版rollbackを対象外と明記し、同版再導入とデータ・設定rollbackを実証。

第三者試験票に必ず記録する:

- clean / updateの初期状態
- OS build、CPU、RAM、空き容量
- installer名、版、SHA
- Ollama、Python、WebView2の初期状態
- 最初の回答までの所要時間、支援回数、合否
- 失敗した手順、画面、error code、復旧結果

### Stage S: Markdown Skill Manager

入口条件を次のように固定する。

- Gate R0合格後: 既存計画との差分監査とテスト設計だけ開始可能。
- Gate U0、M0、D0合格後: Skill専用worktreeで製品実装を開始可能。
- 配布基盤のshared file変更がmergeされ、baselineが再合格した後: Skill変更を製品へ統合可能。

Directorは入口条件とmerge queueをTask開始時にreadbackする。

#### Gate 4

- `SKILL.md`が正本。
- parserはpath escape、重複version、破損frontmatterを拒否。
- developmentとholdoutを分離。
- 固定評価と安全項目に合格し、明示review後だけcandidate化。
- candidateのhashを再確認し、明示承認後だけ昇格。
- Skillを通常チャット、Plugin、Memory、Knowledgeへ自動適用しない。
- Ollama停止時も既存チャット・データの閲覧とSkill管理は可能。新しいAI回答は開始せず、復旧案内を表示。
- Tauriアプリで管理、評価、承認、終了cleanupを確認。

詳細Taskは既存のMarkdown Skill Manager計画をそのまま使用し、重複する新計画を作らない。

### Stage V / E: 隔離比較

Gate 4合格後に開始する。VoiceとModelはPC資源と実測条件が競合するため、同時実行しない。推奨順はVoice、次にModelとする。

#### Gate V0 / V1

- V0でcandidate、revision、license、容量、実行PC、導入commandを提示し、取得前に承認。
- 隔離venvと共通adapter contractを使用。
- fake backend contract、日本語10文、cold/warm first audio、停止、LLM同時負荷、人評価を記録。
- 音声入力ASR、Voice clone、VoiceDesign、installer同梱、標準音声化は対象外。
- 毎回TTS offで既存チャット回帰を確認。
- 音声をMemoryへ自動保存しない。

#### Gate E0 / E1

- E0でartifact ID、revision、license、容量、空き容量、実行PCを提示し、取得前に承認。
- 承認したartifactだけをlocal-onlyで実測。
- 同一20件、3 run、同じPC内で比較。
- 理論診断と実測結果を分けて表示。
- 自動download、自動削除、Router変更、標準採用、localStorage変更は対象外。

### Stage X: 将来拡張

Stage Xは機能ごとに入口条件が異なる。本設計だけで実装を始めず、入口Gate合格後に個別specを作る。

#### Company Memory

- 入口はGate REL0とGate 4の合格後。
- CM0: `scopeType=company`、owner、visibility、根拠、期限、論理削除を個人Memoryから分離。
- CM1: 保存前確認、会社/project越境拒否、編集、忘却、監査を確認。
- 既存Local Context Coreを置換・複製せず、scope adapterで分離する。
- 既存DB一括移行、自動記憶、クラウド同期はしない。

#### P2P

- 入口はGate REL0、Gate 4、CM0の合格後。
- P2P0: 架空fixtureとloopbackだけでpeer認証、hash、size、再送、取消を検証。
- P2P1: 送受信双方の承認、端末失効、監査、上書き防止を実装。
- 管理者ポリシー完成まで`company` scopeはdeny。
- SNS、Cookie、ログイン情報、外部書き込みを扱わない。

#### VRM

- VRM0の入口はGate REL0合格後。Voice/Model比較の完了を必須にしない。
- VRM0: 初期OFF、ローカル許可assetだけを表示。無効時は既存チャットへ完全復帰。
- VRM1の入口はVRM0合格後。Phase 3 fixture/contractまたは別の採用Gateで承認されたengineだけを使う。
- Gate V1の比較結果を自動採用しない。
- Memory/ASRの置換、親密度、自動記憶、外部AI接続はしない。

## 6. 並行実行とmerge順

### 6.1 並行してよい作業

- エンジニア2: release設計、CI、実機試験準備
- ユーザー対応: 文書、第三者試験票、診断項目
- 追加機能担当: 次Gateの差分監査、fixture、テスト設計

### 6.2 並行してはいけない作業

- 同じshared fileへの実装
- VoiceとModelの実機ベンチ
- Mac/Windows成果物の署名と別release commitへの変更
- Company MemoryとP2Pの実データ接続

### 6.3 merge queue

推奨順:

1. R0正本・version・成果物対応
2. U0文書矛盾解消
3. Mac公開source整合とWindows D0設計
4. 配布基盤の最小実装
5. Gate 4 Skill Manager
6. Voice V0/V1
7. Model E0/E1
8. Company Memory / P2P / VRMの個別設計

外部証明書、実機、第三者試験を待つ間は、別worktreeで次工程の読み取り・設計・テスト作成まで進められる。ただし前Gate合格を必要とする製品統合は行わない。

## 7. 承認境界

Directorは次の操作ごとに、対象、目的、影響、rollbackを示してユーザー承認を得る。

- 依存追加・削除
- model、runtime、外部artifactの取得
- 証明書、秘密情報、署名、公証
- 実機benchmark
- 実機へのinstall、上書き、uninstall、第三者試験
- 署名secretを使うCI実行
- commit、push、PR、merge
- GitHub Release公開
- 外部API、外部通信、production変更
- データ削除、不可逆な移行

コード閲覧、fixture、文書作成、diff確認は安全な範囲でDirectorが継続できる。ローカルテストは、外部取得、証明書利用、秘密情報、実機状態変更を伴わない場合だけ確認不要とする。

## 8. 共通検証

各Taskは次の順で進める。

1. 開始commitと既存差分を確認
2. 失敗テストまたは検証条件を固定
3. 最小変更
4. 対象テスト
5. 全体回帰
6. `git diff --check`
7. 実機または画面確認
8. rollback確認
9. 担当外レビュー
10. Director Gate判定

報告では必ず次を分ける。

- 実行して合格したもの
- baselineで既に失敗していたもの
- 環境不足で未実行のもの
- ユーザー承認待ちのもの

## 9. 停止条件

次の場合は担当者が実装を止め、Directorへ返す。

- 正本commit、版番号、成果物の対応が崩れた。
- shared fileを別担当が変更中。
- 未承認の依存、artifact、証明書、秘密情報が必要。
- 外部通信またはデータ削除が新たに必要。
- ユーザーデータの保存先・移行・忘却が曖昧。
- baseline失敗と新規不具合を分離できない。
- 既存マスター計画と本設計が矛盾。

## 10. 完了条件

本プログラムの「配布版完成」は次をすべて満たした時だけ宣言する。

- MacとWindowsが同じ追跡可能な版から生成。
- Macは署名・公証、Windowsは署名を確認。
- 両OSで第三者の新規・更新・削除・再導入・復旧が合格。
- 初心者がターミナルなしで最初の質問まで完了。
- 安全な診断情報を利用者自身がコピーできる。
- Gate 4が合格し、Voice/Modelの採用判断は実測結果として別に保存。
- 既存チャット、Memory、Knowledge、教材、設定を失わない。
- データ・設定rollbackと、対象版が存在する場合のアプリ版rollbackを実証。

Company Memory、P2P、VRMはこの完了条件に含めず、それぞれの専用Gateで判断する。
