# Windows 未署名テストMSI build証跡

## 対象と固定入力

| 項目 | 値 | 状態 |
| --- | --- | --- |
| immutable workflow ref | `w1-private-test-0.8.233-50e4068` | confirmed |
| approved source commit | `50e4068e0cffc8c1254ac3e01dbc691d860fb5f9` | confirmed |
| approved source tree | `bb6d741e5de5526d5b1730bd28c96156b4b0448e` | confirmed |
| workflow source tree | `bb6d741e5de5526d5b1730bd28c96156b4b0448e` | confirmed |
| source version | `0.8.233` | confirmed |
| channel | `private_test_unsigned` | confirmed |
| runner | `windows-2022` | confirmed |
| workflow retention-days | `7` | confirmed |

## GitHub Actions 実行とartifact metadata

| 項目 | 値 | 状態 |
| --- | --- | --- |
| run ID | `30866542496` | confirmed |
| run URL | https://github.com/ShibaPapaMikami/tomos-ai-local-webui/actions/runs/30866542496 | confirmed |
| workflow | `Build Windows installer` | confirmed |
| 実行状態 | `completed` / `success` | confirmed |
| artifact ID | `8876308933` | confirmed |
| artifact name | `TOMOS-AI-UNSIGNED-TEST-ONLY-private_test_unsigned-0.8.233` | confirmed |
| metadata size | `346917` bytes | confirmed |
| expired | `false` | confirmed |
| created_at | `2026-08-04T00:45:16Z` | confirmed |
| expires_at | `2026-08-11T00:45:16Z` | confirmed |

API metadataはrun ID、workflow名、head branch / SHA、event、artifact ID / name、未失効、`10485760` bytes以下を再照合した。`retention-days: 7`はworkflow契約の値であり、APIの`created_at` / `expires_at`とは別に記録する。archive download URLおよびtokenは保存していない。

## 静的archive検証

artifact raw ZIPは新規の一時directoryへだけ取得した。取得後の実archiveは`346917` bytesで、10 MiB上限以下を確認してから展開した。ZIP entryは次のexact 2件だけであり、path traversal、symlink、nested entryはなかった。MSIは実行していない。

| 成果物 | size | SHA-256 | 状態 |
| --- | ---: | --- | --- |
| `TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.msi` | `385024` bytes | `deaf157e1026ff5e943f181464b20e82a3ce836d64152ecac8d616c6b7362941` | confirmed |
| `TOMOS_AI-v0.8.233-windows-UNSIGNED-TEST-ONLY.NOTICE.txt` | `157` bytes | `6397f1e02f913342e9f403b7c916221489e33396248c0984bc3eb654c65a67f1` | confirmed |

NOTICEでは次の固定5行を確認した。

- `UNSIGNED`
- `TEST ONLY`
- `This installer is not a production release.`
- `Do not disable Windows protection.`
- `Before use, verify the Director-provided MSI SHA-256.`

成功・失敗・中断のいずれでもcleanupするtrapを一時directory作成直後に設定し、成功後にそのexact temporary directoryが削除済みであることをreadbackした。artifact bytesはリポジトリに保存していない。

## 境界と未確認事項

- これは`unsigned` / `test-only` / `non-production`の非公開artifact証跡である。GitHub Releaseは作成しておらず、公開URLやRelease assetはない。
- M0 v1 `0.8.234` manifestには、このW1 private-testのversion、commit、tree、run ID、artifact名、size、SHA-256を記録しない。
- Windows実機、Authenticode、Windows保護画面、install、update、uninstall、再導入は未確認である。
