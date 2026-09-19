# 客先環境の疑似CPFログイン停止

## 環境別設定

- 客先検証：`infrastructure/config/customer-validation.json` の `enableDevelopmentCpfMock=false`。
- 自社開発：`infrastructure/config/development-ci.json` の `enableDevelopmentCpfMock=true` と `developmentCpfPasswordRequired=true` を維持。
- フロントエンド・バックエンド双方に同じ環境変数を設定する。ローカルComposeも同じフラグを使用する。

## 無効時の動作

`/development/cpf` は404となり入力フォームを表示しない。`/api/v1/auth/development/config`、`/token`、`/cpf` は利用不可。停止前に発行した疑似CPFトークンによる新規セッション作成も拒否する。正式CPFの `/sso/cpf` と `/api/v1/auth/cpf` は維持する。

ログアウト後、疑似CPFが無効の場合はトップへ遷移し、CPFから入り直す案内を表示する。有効な自社環境では疑似CPF画面へ遷移する。

## 既存セッション

ログイン済みセッションは失効させない。DBに正式・疑似の発行元区分がないため疑似セッションだけの選択的失効はできない。既存セッションはログアウトまたは期限切れまで有効（既定8時間）。

## デプロイ後確認

CloudFormation出力 `DevelopmentCpfMockEnabled` に応じてスモークテストを分岐する。客先では疑似画面・APIの404と未認証管理APIの401を確認する。認証済みチャット確認はSKIPと明記し、正式CPF経由で別途確認する。自社では従来のパスワード付き疑似ログイン・チャット確認を実行する。

2026年9月18日版Word文書にある「客先も疑似CPF有効」「停止すると現行スモークテストが失敗する」という記載は、この変更以降は本書に読み替える。
