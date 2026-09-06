# IAM・機密情報の取扱い

## CDK実行者

初回の`cdk bootstrap`は、客先のAWS管理者が実施してください。日常のデプロイ担当者へ長期の管理者権限を付与せず、CDK Bootstrapが作成するデプロイロール／CloudFormation実行ロールを引き受ける方式を推奨します。

本スタックはVPC、EC2、ECS、ECR、Elastic Load Balancing、RDS、S3、Secrets Manager、IAM、CloudWatch Logs、EventBridge Scheduler、SQS、ACM、Bedrock、OpenSearch Serverless、およびRoute 53（設定時）を扱います。客先の権限境界、SCP、タグ必須ルールがある場合、CDK実行前に客先AWS管理者が確認してください。

デプロイ担当者に必要な代表的権限は次のとおりです。

- CloudFormationスタックの作成・更新・参照
- CDK Bootstrap用S3／ECRへの成果物登録
- Bootstrapの各ロールに対する`sts:AssumeRole`
- 変更セットの作成・実行
- CloudFormation出力とイベントの参照

個別サービスの作成権限を利用者へ直接大量付与するのではなく、CloudFormation実行ロールへ集約します。最小権限ポリシーは、客先のPermission Boundaryと組織ポリシーを確認したうえで、合成したCloudFormationテンプレートのリソース種別から客先AWS管理者が確定してください。

## アプリケーションの実行権限

CDKは用途別にECSタスクロールを作成します。

- Backend: 文書S3の読み書き、Bedrock Retrieve／RetrieveAndGenerate、ワーカー起動
- Worker: 文書S3の読み書き、Bedrock取り込みジョブ、モデル呼び出し
- Bedrock Knowledge Baseサービスロール: S3読取、埋め込みモデル呼び出し、OpenSearch Serverlessデータアクセス
- ECS実行ロール: ECRイメージ取得、CloudWatch Logs出力、必要なSecret読取
- Scheduler: 指定Workerタスクの起動とDLQ送信

既存S3、Knowledge Base、推論プロファイル側に別途Resource Policyやサービスロール制約がある場合は、生成されたタスクロールARNを許可対象へ追加します。

## Gitへ保存しない値

- `config/*.json`の実値ファイル
- CPFの秘密鍵（チャットボット側では受領・保管しない）
- CPF公開鍵の実値JSON
- DBパスワード
- Cookie／JWT署名用Secret
- AWSアクセスキー、セッショントークン

DB、開発用JWT、匿名化用SecretはCDKがSecrets Managerへ生成します。CPF公開鍵もSecrets Managerへ登録し、更新後にBackend ECSサービスを再起動します。

## 客先へ渡してよいもの

- CDKソースコードとサンプル設定
- Knowledge Base ID／Data Source IDの項目名と設定手順
- CloudFormation出力名
- CPF公開鍵の登録形式
- 構築・更新・復旧・削除手順

実値を含む設定ファイルは、客先の承認済みの秘密情報共有経路で客先内だけに保管します。
