# F-020：H+さん検証環境向けポリシー修正案（第2版）

対象：`ScholarshipChatbot-stg01-demo`（AWSアカウント `796575284584`、東京リージョン）。2026年9月28日作成。

## H+さんにお願いする作業

1. IAMのカスタマー管理ポリシー **ScholarshipChatbotCfnExec2Data** の現在のJSONを控えてください。
2. **ScholarshipChatbotCfnExec2Data.proposed.json の全文**で同ポリシーの新しいバージョンを作成し、デフォルトバージョンに設定してください。追加ポリシーとして併用するものではありません。
3. **ScholarshipChatbotAppBoundary、ScholarshipChatbotCfnExec1Infraは今回変更しません。**
4. 弊社からデプロイ準備完了の連絡後、bootstrapのCloudFormation実行ロールを、AdministratorAccessではなく、上記CfnExec1Infra・CfnExec2Dataを使用する構成へ更新してください。AdministratorAccessが残っていないことをご確認ください。
5. ポリシー・bootstrapの更新完了をご連絡ください。実環境の設定が共有済みJSONから変わっている場合は、差し替える前に変更内容をご共有ください。

## 今回の修正内容

以前の説明では条件キーでOpenSearchのポリシー操作を限定する案を記載しました。今回お渡しするJSONは、その案に代わる **今回の移行で不要な管理操作を禁止する案** です。混在した規則への条件判定を未検証のまま許可に使用しません。

変更するのはCfnExec2DataのOpenSearch Serverless部分のみです。

- `OpenSearchServerlessCollection` を削除します。
- `OpenSearchServerlessPoliciesNoResourceLevelSupport` を削除します。
- `OwnOpenSearchServerlessCollection` からTagResource・UntagResourceを外します。
- `DenyAossProvisioningAndPolicyChangesDuringMigration` を追加し、コレクション新規作成、タグの追加・削除、アクセス/セキュリティポリシーの作成・変更・削除の9操作を明示的に禁止します。
- 既存の対象コレクションに限定したAPIAccessAll・UpdateCollection・DeleteCollectionは維持します。他のサービスに関する記述は変更しません。

**これは既存環境のBoundary付与・証明書管理移行用です。新規環境の構築用ではありません。** 今後、禁止したOpenSearch管理操作を伴うCDK変更、コレクションの作り直し、スタック全体の削除が必要になった場合には、事前に権限を見直す必要があります。自動デプロイがそれらの操作を必要とした場合は権限エラーで停止します。

チャットの検索・回答生成・学習用データの取り込みを行うアプリのロールとBoundaryは変更しません。実稼働での動作はデプロイ後に弊社で確認します。

## 弊社が担当する作業

- 修正案JSONの作成、構文・認可判定の確認。
- 8 IAMロールのBoundary付与と、共用ListenerCertificateにRetainを設定するコードの準備（準備済み）。
- デプロイ前の変更内容確認。OpenSearchの管理操作が含まれる場合はそのまま実行せず、必要な権限・変更内容を整理します。
- H+さんのbootstrap更新完了後、Pushと自動デプロイの確認。
- 保存されたテンプレートのRetainを確認後、証明書を残したままCDK管理から外す2回目のデプロイ。
- チャット、ファイル取込、KB取り込みの動作確認。

同時刻の作業は不要です。H+さんのbootstrap更新完了後に弊社のデプロイを進めます。

## 初回更新が失敗した場合

CfnExec1InfraのDeleteRolePermissionsBoundary禁止は変更しません。初回のBoundary付与後に更新が失敗し、Boundaryなしの状態へ戻そうとすると、ロールバックも停止する可能性があります。
弊社でCloudFormationイベントと復旧手順を確認し、管理権限での操作が必要な場合に限りH+さんへ具体的に依頼します。禁止設定やAdministratorAccessを自動的に緩和する運用にはしません。

## 検証結果と範囲

- AWS IAM Access Analyzerによる修正案の検証：指摘なし。
- IAMシミュレーターで9操作の明示的拒否と、対象コレクションの許可・対象外コレクションの不許可を確認。これは入力JSONに対する認可判定で、実APIの実行試験ではありません。
- 元JSONと比較し、上記OpenSearch部分以外は変更していないことを確認。
- CDKの構造試験では、第1段階は8ロールのBoundaryと証明書のRetain、第2段階は証明書管理定義の除去のみを確認。構造試験は仮のネットワーク参照情報を使用しており、そのテンプレートを実環境へのデプロイには使用しません。
- H+さんのAWSに適用された全ポリシーの確認、制限後の実デプロイ・動作・ロールバック試験は未実施です。

## 先行資料の補足・訂正

前の資料の「コレクション作成・タグ操作のARN指定は許可として働かない」という一括した断定は取り下げます。AWSの認可表ではリソース指定が記載されていない一方、AWS管理ポリシーにはTagResourceにcollection ARNを指定する例があり、タグ操作を一律に無効と断定できません。今回の削除・禁止は、その断定を根拠にしたものではなく、今回不要な管理権限を与えないためです。

条件キーを使う前の資料ではなく、本資料と第2版JSONを使用してください。

## 参考資料

- [AWS OpenSearch Serverless認可表](https://docs.aws.amazon.com/service-authorization/latest/reference/list_opensearchserverless.html)
- [条件キーの説明](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/security-iam-serverless.html)
- [AWS管理ポリシーのTagResource指定例](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/CloudWatchOpenSearchDashboardsFullAccess.html)
