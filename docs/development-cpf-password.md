# 自社開発環境の疑似ログイン用共通パスワード

- 自社用 `infrastructure/config/development-ci.json` の `developmentCpfPasswordRequired: true` で有効にする。
- 客先検証設定は変更していない。フラグ未指定では従来どおりパスワード不要。
- AWS Secrets Managerが32文字のランダムパスワードを生成し、バックエンドコンテナの `CPF_DEVELOPMENT_PASSWORD` に渡す。値をコード・フロントエンド・CloudFormation出力には含めない。
- CloudFormation出力 `CpfLoginPasswordSecretName` は秘密値ではなく保存先名。許可されたAWS管理者がSecrets Managerで値を取得し、開発メンバーへ社内の安全な経路で共有する。
- `CPF_DEVELOPMENT_PASSWORD_REQUIRED=true` で秘密値が未設定の場合、ログインを拒否する。
- トークン発行APIで比較するため、画面を経由しない呼び出しもパスワードが必要。
- 設定取得APIはパスワード要求有無だけを返す。疑似ログイン無効時は404。
- 自動検証スクリプトもSecrets Managerから値を取得する。実行ロールに対象シークレットのGetSecretValue権限が必要。
- パスワード変更後はバックエンドの新タスクへの更新が必要。既存ログインセッションはパスワード変更だけでは失効しない。
- 客先で疑似ログインを停止する際は、共通コードの削除ではなく環境別の無効化またはルート遮断で自社環境と分離する。
