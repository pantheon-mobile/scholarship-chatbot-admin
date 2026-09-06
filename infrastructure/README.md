# AWS CDK deployment

このディレクトリは、ローカル開発用のDocker Composeを残したまま、同じアプリをAWSへ配置するためのCDK定義です。

## 作成するリソース

- 2 Availability ZoneのVPC（公開、アプリ、DBサブネット）
- Application Load Balancer
- Frontend／BackendのECS Fargateサービス
- 変換・同期用のECS Fargateタスク
- EventBridge Schedulerによる夜間実行（標準は毎日01:00 JST）
- PostgreSQL 16のRDS、DB認証情報用Secrets Manager
- CPF公開鍵、開発用JWT、匿名化用Secret
- CloudWatch Logs、夜間タスク起動失敗用SQS DLQ
- 文書S3バケット（既存バケット名を指定した場合は新規作成しない）
- 任意でOpenSearch Serverless、ベクトルインデックス、Bedrock統合Knowledge Base、形式別6 Data Source

CDKはFrontendとBackendのDockerイメージをビルドし、CDK管理のECRへ登録してからECSへ反映します。初回だけECRが空になってECS起動に失敗することはありません。

## 事前準備

1. Node.js 20以上、Docker、AWS CLI、AWS CDKを利用可能にします。
2. 自社開発では`config/development.example.json`、客先検証では`config/customer-validation.example.json`を実値ファイルへコピーします。実値ファイルはGit管理対象外です。
3. 既存の統合Knowledge Baseが参照するS3バケットを使う場合、`existingDocumentsBucketName`にはそのバケット名を指定します。空にした場合はCDKが新規バケットを作ります。
4. HTTPSを使う場合は同じリージョンのACM証明書ARNと`domainName`を設定します。Route 53も同じAWSアカウントで管理する場合だけHosted Zoneの3項目を設定します。
5. `provisionKnowledgeBase=true`ではOpenSearch Serverless、統合KB、PDF／Web／Excel／Word／PowerPoint／Text用Data Sourceを自動作成し、生成IDをECSへ設定します。既存KBを利用する場合だけ`false`にしてデプロイ時に各IDを渡します。

客先AWS環境へ引き渡す場合は、[`CUSTOMER_HANDOFF.md`](CUSTOMER_HANDOFF.md)、[`PRE_DEPLOY_CHECKLIST.md`](PRE_DEPLOY_CHECKLIST.md)、[`IAM_AND_SECURITY.md`](IAM_AND_SECURITY.md)を使用し、`config/customer-validation.example.json`から客先専用の実値設定を作成してください。

## 構成の確認

```bash
cd infrastructure
npm ci
npm run build
npm run synth -- --context config=config/development.json
```

## 初回デプロイ

対象アカウントとリージョンを必ず確認してから実行します。

```bash
aws sts get-caller-identity
npx cdk bootstrap aws://<AWS_ACCOUNT_ID>/ap-northeast-1
npx cdk deploy --context config=config/development.json \
  --parameters ChatKnowledgeBaseId=<統合KB_ID> \
  --parameters ChatModelArn=<Claude_Sonnet_4.6推論プロファイルARN> \
  --parameters PDFKnowledgeBaseId=<PDF_KB_ID> --parameters PDFDataSourceId=<PDF_DS_ID> \
  --parameters WEBKnowledgeBaseId=<WEB_KB_ID> --parameters WEBDataSourceId=<WEB_DS_ID> \
  --parameters EXCELKnowledgeBaseId=<EXCEL_KB_ID> --parameters EXCELDataSourceId=<EXCEL_DS_ID> \
  --parameters WORDKnowledgeBaseId=<WORD_KB_ID> --parameters WORDDataSourceId=<WORD_DS_ID> \
  --parameters PPTKnowledgeBaseId=<PPT_KB_ID> --parameters PPTDataSourceId=<PPT_DS_ID> \
  --parameters TEXTKnowledgeBaseId=<TEXT_KB_ID> --parameters TEXTDataSourceId=<TEXT_DS_ID> \
  --parameters CpfFacultyReturnUrl=<CPF教職員URL> \
  --parameters CpfStudentReturnUrl=<CPF学生URL>
```

CloudFormationの出力`ApplicationUrl`が接続先です。外部DNSを使用する場合は、出力`LoadBalancerDnsName`をCNAME値として登録します。デプロイはRDS、NAT Gateway、ALB、ECSなどの利用料金を発生させます。

## CPF公開鍵の設定

デプロイ後、CloudFormation出力`CpfPublicKeysSecretName`のSecret値を、CPFから受領した`kid`とPEM公開鍵のJSONへ更新します。

```json
{
  "cpf-chatbot-stg-202609": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
}
```

ECSのSecret環境変数はタスク起動時に読み込まれるため、更新後はBackendサービスを「新しいデプロイの強制」で再起動します。

## データベース移行と動作確認

Backendタスク起動時に`alembic upgrade head`を実行します。デプロイ後は次の順で確認します。

1. `/api/v1/health`が`{"status":"ok"}`を返す。
2. 開発環境では`/development/cpf`からadmin／staffでログインできる。
3. ファイルとWebサイトを1件ずつ登録する。
4. 「今すぐ実行」で専用ECSワーカーが起動し、データソースが利用可能になる。
5. チャットで登録内容を質問し、回答と参照元を確認する。
6. 夜間スケジュールとDLQ、Backend／WorkerのCloudWatch Logsを確認する。

## ローカル開発との使い分け

- 通常の画面・API・DB変更: `docker compose up --build`
- ローカルアプリからAWS開発用S3／Bedrockへ接続: `compose.aws-dev.yaml`と`.env.aws-dev`
- AWS上での統合試験: このCDKスタック

したがってAWS環境を作成した後も、ローカル環境は短時間の実装・テスト用途として残します。環境差は環境変数とCDK設定だけに限定します。
