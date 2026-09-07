# 客先引渡し前 AWS再現試験結果

- 実施日: 2026-09-07
- リージョン: `ap-northeast-1`
- 対象コミット: `fd796cd`
- GitHub Actions: `Pre-handoff AWS rehearsal` run `34088427050`
- 結果: 成功

## 自動確認結果

| 結果 | 確認項目 |
|---|---|
| PASS | Frontendページ表示 |
| PASS | BackendヘルスチェックとPostgreSQL接続 |
| PASS | Frontend ECSサービス安定稼働 |
| PASS | Backend ECSサービス安定稼働 |
| PASS | OpenSearch Serverless／統合Knowledge Base利用可能 |
| PASS | PDF＋Text／Web／Excel／Word／PowerPointの5 Data Source作成 |
| PASS | CPF疑似ログイン |
| PASS | 認証セッション |
| PASS | チャットUI設定取得 |
| PASS | Bedrock RAG回答生成 |

## 補足

この実行では`website_test_url`を指定していないため、任意試験であるWebサイト登録後のクロール、変換、S3配置、Knowledge Base同期は実行していません。この通し試験は客先受入時に許可された検証URLを指定して実施します。

一時環境は調査・追加確認用に`KEEP`で残しています。不要になった時点で、対象アカウントと保持データを確認したうえで明示的に削除します。
