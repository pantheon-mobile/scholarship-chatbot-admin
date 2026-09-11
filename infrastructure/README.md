# AWS CDK deployment

このディレクトリは、ローカル開発用のDocker Composeを残したまま、同じアプリをAWSへ配置するためのCDK定義です。

## 作成するリソース

- 2 Availability ZoneのVPC（公開、アプリ、DBサブネット）。客先検証環境では既存VPC・指定サブネットを利用
- Application Load Balancer。客先検証環境では既存ALB・HTTPSリスナーへホストベースルールを追加
- Frontend／BackendのECS Fargateサービス
- 変換・同期用のECS Fargateタスク
- EventBridge Schedulerによる夜間実行（標準は毎日01:00 JST）
- PostgreSQL 16のRDS、DB認証情報用Secrets Manager
- CPF公開鍵、開発用JWT、匿名化用Secret
- CloudWatch Logs、夜間タスク起動失敗用SQS DLQ
- 文書S3バケット（既存バケット名を指定した場合は新規作成しない）
- 任意でOpenSearch Serverless、ベクトルインデックス、Bedrock統合Knowledge Base、形式別5 Data Source

CDKはFrontendとBackendのDockerイメージをビルドし、CDK管理のECRへ登録してからECSへ反映します。初回だけECRが空になってECS起動に失敗することはありません。

## 事前準備

1. Node.js 20以上、Docker、AWS CLI、AWS CDKを利用可能にします。
2. 自社開発では`config/development.example.json`を実値ファイルへコピーします。客先検証環境では設定済みの`config/customer-validation.json`を使用し、客先での編集は不要です。
3. 既存の統合Knowledge Baseが参照するS3バケットを使う場合、`existingDocumentsBucketName`にはそのバケット名を指定します。空にした場合はCDKが新規バケットを作ります。
4. HTTPSを使う場合は同じリージョンのACM証明書ARNと`domainName`を設定します。Route 53も同じAWSアカウントで管理する場合だけHosted Zoneの3項目を設定します。
5. `provisionKnowledgeBase=true`ではOpenSearch Serverless、統合KB、PDF＋Text／Web／Excel／Word／PowerPoint用の5 Data Sourceを自動作成し、生成IDをECSへ設定します。TXT／CSVはPDF Data SourceとS3 prefixを共用します。既存KBを利用する場合だけ`false`にしてデプロイ時に各IDを渡します。
6. 客先検証環境では既存HTTPSリスナーにAPI用`1001`、画面用`1002`の2ルールを作成します。デプロイスクリプトが両方の未使用を確認します。

客先AWS環境へ引き渡す場合は、[`CUSTOMER_HANDOFF.md`](CUSTOMER_HANDOFF.md)、[`PRE_DEPLOY_CHECKLIST.md`](PRE_DEPLOY_CHECKLIST.md)、[`IAM_AND_SECURITY.md`](IAM_AND_SECURITY.md)を使用してください。

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
  --parameters ChatModelArn=<Claude_Sonnet_4.6推論プロファイルARN> \
  --parameters CpfFacultyReturnUrl=<CPF教職員URL> \
  --parameters CpfStudentReturnUrl=<CPF学生URL>
```

上記は`provisionKnowledgeBase=true`の標準構成です。OpenSearch Serverless、統合Knowledge Base、5つのData SourceをCDKが作成し、生成したIDをECSへ自動設定します。

### 客先検証環境

客先検証環境では、AWS CLIで対象アカウントへログインして次を実行します。

```bash
cd infrastructure
./scripts/deploy-customer-validation.sh
```

スクリプトは、AWSアカウント`796575284584`、東京リージョン、既存ALBのルール優先順位、Claude Sonnet 4.6推論プロファイルを確認してから、依存関係の導入、ビルド、CDK bootstrap、deployを実行します。推論プロファイルを自動検出できない場合だけ、確認済みARNを環境変数で渡します。

```bash
CHAT_MODEL_ARN=<推論プロファイルARN> ./scripts/deploy-customer-validation.sh
```

既存Knowledge Baseを使うため`provisionKnowledgeBase=false`とした場合だけ、`ChatKnowledgeBaseId`と形式別のKnowledge Base ID／Data Source IDを追加指定します。PDFとTXT／CSVでData Sourceを共用する構成では、`TEXTKnowledgeBaseId`と`TEXTDataSourceId`にPDFと同じ値を指定します。

CloudFormationの出力`ApplicationUrl`が接続先です。外部DNSを使用する場合は、出力`LoadBalancerDnsName`をCNAME値として登録します。デプロイはRDS、NAT Gateway、ALB、ECSなどの利用料金を発生させます。

## CPF公開鍵の設定

デプロイ後、CloudFormation出力`CpfPublicKeysSecretName`のSecret値を、CPFから受領した`kid`とPEM公開鍵のJSONへ更新します。

```json
{
  "cpf-chatbot-stg-202609": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
}
```

ECSのSecret環境変数はタスク起動時に読み込まれるため、更新後はBackendサービスを「新しいデプロイの強制」で再起動します。

客先検証環境では、受領した公開鍵ファイルをGit管理外の場所へ保存して次を実行します。鍵形式確認、Secrets Managerへの登録、Backend ECSの再起動と安定稼働待機まで自動実行します。

```bash
cd infrastructure
./scripts/register-cpf-public-key.sh /path/to/chatbot_cpf_stg_public.pem
```

CPF側の接続先は`https://ai-chatbot-stg01-demo.gakupita.com/sso/cpf`です。

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

## 客先引渡し前の自動再現テスト

GitHub Actionsの`Pre-handoff AWS rehearsal`を手動実行すると、空環境からCDKをデプロイし、次を自動確認してMarkdownレポートをArtifactsへ保存します。

- FrontendとBackendの到達性
- Backend、RDSのヘルスチェック
- Frontend／Backend ECSサービスの安定稼働
- 統合Knowledge Baseの`ACTIVE`
- CPF疑似ログインと認証セッション
- チャット設定取得とBedrock RAG回答生成
- 任意でWebサイト登録、取り込みワーカー起動、変換・Knowledge Base同期完了待ち

事前にGitHub Actions Secretsへ以下を登録します。

- `AWS_REHEARSAL_ROLE_ARN`: GitHub OIDCから引き受けるCDKデプロイ用IAM Role ARN
- `CHAT_MODEL_ARN`: Claude Sonnet 4.6の推論プロファイルARN

実行時の`cleanup_confirmation`は標準で`KEEP`です。調査用に環境を残さない場合だけ、明示的に`DESTROY`と入力します。`deletionProtection=false`の再現テスト環境では、CDK管理のS3とRDSも後片付けできる設定になります。本番・開発用設定の保持／スナップショット方針は変わりません。

ローカル端末から同じ処理を行う場合は、`config/rehearsal.example.json`を`config/rehearsal.json`へコピーし、次を実行します。

```bash
cd infrastructure
CHAT_MODEL_ARN=<Claude_Sonnet_4.6推論プロファイルARN> npm run rehearsal
```

Web登録まで確認する場合は`SMOKE_TEST_WEBSITE_URL`を追加します。自動削除まで行う場合だけ`DESTROY_AFTER_TEST=true`を追加してください。

2026年9月7日の実アカウント再現試験では、CDKデプロイ、Frontend／Backend、RDS、ECS、OpenSearch Serverless、統合Knowledge Base、5 Data Source、CPF疑似ログイン、認証セッション、チャット設定、Bedrock RAG回答生成まで全項目が成功しています。実行記録は`REHEARSAL_RESULT.md`を参照してください。

## 自社開発環境への継続デプロイ

自社リポジトリでは、`main`へのPushで`CI`が成功した場合に限り、`Deploy development`が起動します。テスト済みの同一コミットをCDKで`ScholarshipChatbot-development`へ反映し、ECSの安定稼働、画面、API、DB、統合Knowledge Base、疑似CPFログイン、チャット回答を確認します。結果は`development-deploy-report-*`としてGitHub ActionsのArtifactsへ保存します。

GitHubのRepository Secretへ次を設定します。

- `AWS_DEVELOPMENT_ROLE_ARN`: GitHub OIDCから自社開発AWSアカウントのCDKデプロイ権限を引き受けるIAM Role ARN

未設定時は既存の`AWS_REHEARSAL_ROLE_ARN`を利用します。自動デプロイ専用ロールへ分離できるまでは既存ロールを再利用できます。既存ロールのGitHub OIDC信頼条件と一致させるため、EnvironmentではなくRepository Secretを使用します。KB ID、Data Source ID、ClaudeモデルARN、CPF戻り先URLは既存CloudFormationスタックのパラメータを読み取り、そのまま引き継ぎます。旧スタックにTEXT用パラメータがない場合はPDF用IDを自動的に共用します。値をGitHub Secretsへ重複登録する必要はありません。

緊急時やPushを伴わない再実行は、GitHubのActionsから`Deploy development`を選び、`Run workflow`で手動実行できます。同じ環境へのデプロイは同時実行されず、先行デプロイの完了後に実行されます。

## 客先検証環境への継続デプロイ

客先リポジトリ`technical-innovation/bpaas-aichatbot`では、`main`へのPush後に`CI`が成功した場合、`Deploy customer validation`が起動します。CDK bootstrapは実行せず、`package-lock.json`で固定したCDK CLI 2.1139.0を使用します。

GitHubのRepository Secretへ次を設定します。

- `AWS_CUSTOMER_VALIDATION_ROLE_ARN`: `arn:aws:iam::796575284584:role/scholarship-chatbot-github-actions-deploy-role`

OIDCセッションは客先IAMロールの最大値に合わせて7,200秒とします。GitHub Environmentは使用しないため、OIDCの`sub`は`repo:technical-innovation/bpaas-aichatbot:ref:refs/heads/main`のままです。
