# 客先AWS環境 構築・引渡し手順

この文書は、`scholarship-chatbot-admin`を客先AWSアカウントへCDKで構築する担当者向けです。自社開発環境のアカウントID、ドメイン、証明書ARN、S3名、Knowledge Base ID等は使用しません。

## 1. 構成

CDKは次を作成します。

- 2AZのVPC、公開／アプリ／DBサブネット、NAT Gateway 1台
- HTTPS Application Load Balancer
- Frontend／Backend用ECS Fargateサービス
- 変換・同期用ECS Fargateタスクと毎日01:00 JSTのScheduler
- PostgreSQL 16 RDS、Secrets Manager、CloudWatch Logs、SQS DLQ
- S3バケット（既存名を指定した場合は既存バケットを参照）
- OpenSearch Serverlessの暗号化・ネットワーク・データアクセスポリシー
- OpenSearch Serverless Vector Searchコレクションとベクトルインデックス
- Bedrock統合Knowledge Baseと形式別5 Data Source（PDF＋Text／Web／Excel／Word／PowerPoint）
- Knowledge Baseサービスロールと必要なIAM権限

## 2. 客先に事前準備いただくもの

- AWSアカウントID、デプロイ先リージョン（標準は`ap-northeast-1`）
- CDKを実行できるIAM権限
- Docker、Node.js 20以上、AWS CLI
- アプリ用FQDNと、同リージョンで発行済みのACM証明書ARN
- 文書保存用S3バケットを既存利用するか、CDKで新規作成するかの方針
- Claude Sonnet 4.6の推論プロファイルARN
- CPFの教職員・学生戻り先URL
- CPFから受領する`kid`とJWT検証用PEM公開鍵

外部DNSを使用する場合、CDKデプロイ後に出力される`LoadBalancerDnsName`をアプリ用FQDNのCNAME値へ登録します。ACM検証用CNAMEは証明書更新にも必要なため削除しません。

## 3. 設定ファイル

```bash
cd infrastructure
cp config/customer-validation.example.json config/customer-validation.json
```

`customer-validation.json`を客先値へ変更します。この実値ファイルはGit管理対象外です。

- `existingDocumentsBucketName`: 空文字ならCDKが暗号化・バージョニング・公開遮断済みS3を新規作成。既存利用時だけバケット名を設定
- `enableDevelopmentCpfMock`: CPF接続準備が整うまでは`true`。疑似ログイン画面は`/development/cpf`
- CPF接続試験を開始する時点で`false`へ変更し、再デプロイする
- `provisionKnowledgeBase`: OpenSearch Serverless、統合KB、形式別Data SourceをCDKで作る場合は`true`
- `embeddingModelArn`: 標準はTitan Text Embeddings v2（1024次元）
- `opensearchDeploymentPrincipalArn`: 標準のCDK Bootstrap以外のCloudFormation実行ロールを使用する場合だけ、そのARNを設定
- `deletionProtection`: 原則`true`
- `hostedZoneId`／`hostedZoneName`: Route 53を同一AWSアカウントで管理する場合のみ設定
- 外部DNSの場合、上記2項目は空文字のままにする

## 4. 事前確認と初回構築

```bash
aws sts get-caller-identity --profile <AWS_PROFILE>
cd infrastructure
npm ci
npm run build
npx cdk bootstrap aws://<AWS_ACCOUNT_ID>/ap-northeast-1 --profile <AWS_PROFILE>
npx cdk diff --profile <AWS_PROFILE> --context config=config/customer-validation.json \
  --parameters ChatModelArn=<推論プロファイルARN> \
  --parameters CpfFacultyReturnUrl=<CPF教職員URL> \
  --parameters CpfStudentReturnUrl=<CPF学生URL>
```

差分をレビュー後、同じ引数で`npx cdk deploy`を実行します。`provisionKnowledgeBase=true`では、KB IDとDS IDはCDKが生成してECSへ自動設定します。コマンド履歴やCIログにURL等が残る点を許容できない場合は、客先CIの保護変数から引数を組み立ててください。

## 5. DNSとCPF公開鍵

1. CloudFormation出力`LoadBalancerDnsName`をDNSへ登録します。
2. `ApplicationUrl`の`/api/v1/health`が`{"status":"ok"}`を返すことを確認します。
3. 出力`CpfPublicKeysSecretName`のSecretを次のJSONへ更新します。

```json
{
  "cpf-chatbot-stg-202609": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
}
```

4. Backend ECSサービスで「新しいデプロイの強制」を実行します。
5. `enableDevelopmentCpfMock`を`false`へ変更して再デプロイします。
6. CPFから`https://<FQDN>/sso/cpf`へ正常JWTをPOSTし、ダッシュボードへ遷移することを確認します。
7. 期限切れ、署名不正、同一`jti`再利用が拒否されることを確認します。

## 6. 受入確認

- admin／staffで表示可能な管理機能が権限表どおりである
- ファイル・Web登録後にジョブが`準備中`になる
- 「今すぐ実行」と夜間Schedulerの双方でワーカーが起動する
- 変換、S3配置、Knowledge Base同期後に`利用可能`になる
- FAQ一致時はFAQ回答、閾値未満ではRAG回答になる
- 回答優先度、参照元リンク設定、Good／Bad評価が反映・保存される
- 操作ログ、アクセスログ、チャット履歴、ユーザリストをExcel形式で取得できる
- CloudWatch LogsとDLQで障害を追跡できる

## 7. 更新・ロールバック

更新前に`git`の対象タグ、DBスナップショット、`cdk diff`を確認し、通常は同じ設定とパラメータで`cdk deploy`します。ECSの新しいタスクがヘルスチェックに失敗するとCircuit Breakerが旧タスクへ戻します。

アプリケーションを明示的に戻す場合は、直前の安定タグをチェックアウトして再度`cdk deploy`します。DBマイグレーションには自動ダウングレードを行いません。破壊的なDB変更は、復元手順を個別に用意してから適用します。

## 8. 削除

通常運用では削除しません。スタックには終了保護、RDSには削除保護が設定されています。削除には、変更申請・バックアップ確認・対象アカウント確認後に両方の保護を明示的に解除する必要があります。

S3は保持、RDSはスナップショット作成を既定としています。`cdk destroy`だけで全データが消える構成ではありません。残存リソースと料金を必ず確認してください。

## 9. 引渡し物

- 本リポジトリのリリースタグ
- `config/customer-validation.example.json`
- 客先内で保管する実値設定（Gitへコミットしない）
- 本書、`PRE_DEPLOY_CHECKLIST.md`、`IAM_AND_SECURITY.md`
- CloudFormation出力一覧
- 自動生成された統合KB ID、形式別Data Source ID、OpenSearch Serverless Collection ARN
- CPF公開鍵の更新・ローテーション手順
- 運用監視先（CloudWatch Logs、ECS、Scheduler、DLQ、RDS）の一覧

具体的なファイル一覧と受渡し時の確認順は`HANDOFF_MANIFEST.md`を参照してください。自社AWSでの再現試験結果は`REHEARSAL_RESULT.md`に記録しています。
