# AWS構築前チェックリスト

## 確定値

- [ ] AWSアカウントIDと`aws sts get-caller-identity`の結果が一致
- [ ] リージョンが`ap-northeast-1`（変更時はBedrockモデル提供状況を再確認）
- [ ] 環境名とアプリ用FQDNが確定
- [ ] ACM証明書が対象リージョンで`ISSUED`
- [ ] DNS管理者と、ALB用CNAME登録手順が確定
- [ ] 既存S3バケット名、またはCDKによる新規作成方針が確定（標準はCDK新規作成）
- [ ] `provisionKnowledgeBase=true`でOpenSearch Serverless／統合KB／形式別DSを作成する方針を確認
- [ ] OpenSearch Serverlessの継続料金を承認済み
- [ ] Claude Sonnet 4.6推論プロファイルARNが確定
- [ ] CPF教職員戻り先URLが確定
- [ ] CPFの`kid`と公開鍵の受領予定が確定

## セキュリティ・運用

- [ ] CPF未接続期間は`enableDevelopmentCpfMock=true`とし、疑似ログインの利用範囲を関係者に限定
- [ ] CPF接続試験前に`enableDevelopmentCpfMock=false`へ変更する計画と担当者を決定
- [ ] `deletionProtection=true`
- [ ] 実値設定ファイルと秘密情報をGitに含めていない
- [ ] CloudFormation変更セットまたは`cdk diff`をレビュー
- [ ] NAT Gateway、ALB、RDS、ECS等の継続料金を承認済み
- [ ] RDSバックアップ保持期間と復旧責任者を確認
- [ ] CloudWatch Logs、Scheduler失敗、DLQの監視担当を決定
- [ ] CPF公開鍵ローテーション時のSecret更新とECS再起動手順を共有

## デプロイ後

- [ ] CloudFormationが`CREATE_COMPLETE`または`UPDATE_COMPLETE`
- [ ] OpenSearch Serverless、統合Knowledge Base、5つのData Source（PDF＋Text／Web／Excel／Word／PowerPoint）が作成済み
- [ ] 終了保護とRDS削除保護が有効
- [ ] DNSがALBを参照し、HTTPS証明書エラーがない
- [ ] Frontend／Backend ECSサービスが安定
- [ ] `/api/v1/health`が正常
- [ ] CPF正常系・異常系試験が正常
- [ ] 登録→変換→同期→チャット回答の通し試験が正常
- [ ] 夜間Schedulerと手動実行が正常
- [ ] ログ、DLQ、DBスナップショットを確認
