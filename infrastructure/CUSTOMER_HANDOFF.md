# 客先AWS環境 構築・引渡し手順

この文書は、`scholarship-chatbot-admin`を客先AWSアカウントへCDKで構築する担当者向けです。自社開発環境のアカウントID、ドメイン、証明書ARN、S3名、Knowledge Base ID等は使用しません。

## 1. 構成

CDKは次を作成します。

- 客先既存VPCと指定済み3サブネットへのECS・RDS配置
- 客先既存HTTPS Application Load Balancerへのホストベースルール追加
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
- アプリ用FQDN、既存ALB／HTTPSリスナー／Security Group、同リージョンのACM証明書
- 文書保存用S3バケットを既存利用するか、CDKで新規作成するかの方針
- Claude Sonnet 4.6が対象アカウントで利用可能であること（ARNはデプロイスクリプトが自動検出）
- CPFの教職員・学生戻り先URL
- CPFから受領する`kid`とJWT検証用PEM公開鍵

客先検証環境のDNSは客先が設定します。CDKデプロイ後に出力される`LoadBalancerDnsName`をアプリ用FQDNのCNAME値へ登録します。

## 3. 設定ファイル

客先検証環境の値は`config/customer-validation.json`へ設定済みです。客先でのCDK編集は不要です。

- `existingDocumentsBucketName`: 空文字ならCDKが暗号化・バージョニング・公開遮断済みS3を新規作成。既存利用時だけバケット名を設定
- `enableDevelopmentCpfMock`: CPF接続準備が整うまでは`true`。疑似ログイン画面は`/development/cpf`
- CPF接続試験を開始する時点で`false`へ変更し、再デプロイする
- `provisionKnowledgeBase`: OpenSearch Serverless、統合KB、形式別Data SourceをCDKで作る場合は`true`
- `embeddingModelArn`: 標準はTitan Text Embeddings v2（1024次元）
- `opensearchDeploymentPrincipalArn`: 標準のCDK Bootstrap以外のCloudFormation実行ロールを使用する場合だけ、そのARNを設定
- `deletionProtection`: 原則`true`
- `hostedZoneId`／`hostedZoneName`: Route 53を同一AWSアカウントで管理する場合のみ設定
- 外部DNSの場合、上記2項目は空文字のままにする
- 既存HTTPSリスナーではAPI用優先順位`1001`、画面用優先順位`1002`を使用する

## 4. 事前確認と初回構築

```bash
cd infrastructure
./scripts/deploy-customer-validation.sh
```

スクリプトは対象AWSアカウント、既存ALBのルール優先順位、Claude Sonnet 4.6推論プロファイルを確認してから、ビルド、CDK bootstrap、deployを実行します。`provisionKnowledgeBase=true`のため、KB IDとDS IDはCDKが生成してECSへ自動設定します。

## 5. DNSとCPF公開鍵

1. CloudFormation出力`LoadBalancerDnsName`をDNSへ登録します。
2. `ApplicationUrl`の`/api/v1/health`が`{"status":"ok"}`を返すことを確認します。
3. 受領した公開鍵をGit管理外の場所へ保存し、次を実行します。

```bash
./scripts/register-cpf-public-key.sh /path/to/chatbot_cpf_stg_public.pem
```

4. スクリプトがSecret更新、Backend ECS再起動、安定稼働待機まで実行します。
5. CPF接続準備が完了するまでは疑似ログインを有効のまま使用します。
6. CPFから`https://ai-chatbot-stg01-demo.gakupita.com/sso/cpf#token=<JWT>`へ遷移し、ダッシュボードが表示されることを確認します。
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
- 設定済みの`config/customer-validation.json`
- 本書、`PRE_DEPLOY_CHECKLIST.md`、`IAM_AND_SECURITY.md`
- CloudFormation出力一覧
- 自動生成された統合KB ID、形式別Data Source ID、OpenSearch Serverless Collection ARN
- CPF公開鍵の更新・ローテーション手順
- 運用監視先（CloudWatch Logs、ECS、Scheduler、DLQ、RDS）の一覧

具体的なファイル一覧と受渡し時の確認順は`HANDOFF_MANIFEST.md`を参照してください。自社AWSでの再現試験結果は`REHEARSAL_RESULT.md`に記録しています。
