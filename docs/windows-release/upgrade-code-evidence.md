# Windows MSI UpgradeCodeの読取証跡

## 状態と境界

この文書は承認済みの読取証跡のみを記録する。D0 Gate承認ではなく、署名または公開を
許可しない。この証跡のためのMSI実行、インストール、更新、またはアンインストールは
実施していない。

状態値: `confirmed` = 承認済みの読取結果が利用可能、`blocked` = この証跡記録の範囲外に
残る操作。

## 公開済みMSIと識別情報の読取

| 項目 | 値 | 状態 | 証跡メモ |
| --- | --- | --- | --- |
| リリースURL | https://github.com/ShibaPapaMikami/tomos-ai-local-webui/releases/tag/v0.8.233 | confirmed | 承認済みのリリース読取。 |
| タグcommit | `6df62c09cb64044ed76480e417706ca2167a72ae` | confirmed | 承認済みのリリース読取。 |
| 成果物 | `TOMOS_AI-v0.8.233-windows.msi` | confirmed | 承認済みのリリース読取。 |
| サイズ | `385024` bytes | confirmed | 承認済みのリリース読取。 |
| SHA-256 | `7e3b970d310c5afbbe8967b90282a0d98e6492360212c73e688a8e0b2264045d` | confirmed | 公開ダイジェストおよびローカル静的コピーのダイジェストが一致。 |
| Property table: UpgradeCode | `{7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1}` | confirmed | 承認済みのProperty-table読取。 |
| Property table: ProductCode | `{6825D8D0-ADE7-4467-952D-E1CB9B3866B0}` | confirmed | 承認済みのProperty-table読取。 |
| Property table: ProductVersion | `0.8.233` | confirmed | 承認済みのProperty-table読取。 |
| Property table: ProductName | `TOMOS AI` | confirmed | 承認済みのProperty-table読取。 |
| 現行 `scripts/make-windows-msi.py` のUpgradeCode | `{7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1}` | confirmed | 現行ソースは公開済みMSIのProperty tableと一致。 |

## 一致確認と実行境界

| 確認項目 | 状態 | 証跡メモ |
| --- | --- | --- |
| 公開ダイジェストおよびローカル静的コピーのダイジェスト | confirmed | どちらも記録したMSI SHA-256と一致。 |
| MSI Property tableおよび現行ソース | confirmed | どちらもUpgradeCode `{7FAD4890-85D1-4C8D-A4AA-0B1B7E7F41A1}`を使用。 |
| MSI実行/インストール/更新/アンインストール | blocked | 実施していない。この証跡はruntimeの更新動作を検証しない。 |
| D0 Gate承認 | blocked | 読取証跡はD0 Gate承認ではない。 |
| 署名または公開 | blocked | この文書は署名または公開を許可しない。 |
