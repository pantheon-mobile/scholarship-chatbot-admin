# 客先引渡し物一覧

## 渡すもの

- `scholarship-chatbot-admin`リポジトリの確定リリースタグ
- `frontend/`、`backend/`、`infrastructure/`、DBマイグレーションを含むソース一式
- `infrastructure/config/customer-validation.example.json`
- `infrastructure/CUSTOMER_HANDOFF.md`
- `infrastructure/PRE_DEPLOY_CHECKLIST.md`
- `infrastructure/IAM_AND_SECURITY.md`
- `infrastructure/README.md`
- `infrastructure/REHEARSAL_RESULT.md`

## 客先側だけで保管するもの

- `config/customer-validation.json`の実値
- Claude Sonnet 4.6推論プロファイルARN
- CPFの`kid`とPEM公開鍵
- CPFの環境別戻り先URL
- デプロイ用IAM Role、GitHub Actions Secretsなどの認証情報

これらの実値や秘密情報はGitへコミットしません。

## 引渡し時の実施順

1. リリースタグと対象コミットを合意する。
2. `PRE_DEPLOY_CHECKLIST.md`の「確定値」と「セキュリティ・運用」を確認する。
3. exampleから客先専用設定ファイルを作成する。
4. 客先AWSアカウントとリージョンを確認し、CDK Bootstrapを実施する。
5. `cdk diff`をレビューしてから`cdk deploy`する。
6. DNSへALBのCNAMEを設定する。
7. CPF未接続期間は疑似ログインで受入試験を行う。
8. CPF公開鍵受領後にSecretを更新し、ECSを再起動して実JWTを試験する。
9. 登録、変換、S3配置、KB同期、チャット回答、ログ出力まで確認する。
10. 監視・バックアップ・障害対応の担当者と連絡先を確定する。

## CDKが自動作成する範囲

標準の`provisionKnowledgeBase=true`では、VPC、ALB、ECS、夜間ワーカー、Scheduler、RDS、Secrets Manager、S3、CloudWatch Logs、SQS DLQ、OpenSearch Serverless、ベクトルインデックス、Bedrock統合Knowledge Base、5つのData Sourceおよび関連IAMをCDKが作成します。

外部DNSのCNAME登録、ACM証明書の事前発行、CPF公開鍵の受領、推論プロファイル利用可否の確認は、AWSアカウントや外部組織に依存するため手動確認が必要です。
