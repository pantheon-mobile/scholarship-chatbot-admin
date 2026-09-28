# F-020：H+さん共有ポリシーの確認と反映手順

2026年9月28日。添付JSON、デプロイ済みテンプレート、実リソース一覧、稼働タスクのモデル設定を照合。
本資料は静的確認結果。制限後の実行ロールによるデプロイ・ロールバック試験は未実施。

## 3ファイルの対応

提供順に ScholarshipChatbotAppBoundary、ScholarshipChatbotCfnExec1Infra、ScholarshipChatbotCfnExec2Data。
JSON自体にポリシー名はないため、内容から対応付けた。Boundary ARNは既に共有されたものを使用。
`.received.json` は共有内容の整形コピーであり、修正済みポリシーではない。

## アプリ側の準備

- H+さん設定の8つのIAMロールへ共有Boundary ARNを設定。
- 自社環境はBoundary設定なしの既存動作を維持。
- 共用ListenerCertificateは、まずDeletionPolicyとUpdateReplacePolicyをRetainにする。
- 初回更新完了・保存テンプレートのRetain確認後、設定をexternalにし、証明書のCDK管理を外す。
- デプロイ済み証明書にRetainがまだないため、2段階を1回の更新にまとめない。
- BoundaryのS3バケット、KB、AOSSコレクション、モデルARNは照合した実環境と一致。これは全APIの動作保証ではない。

## bootstrap更新前に修正する項目

### OpenSearch Serverlessのポリシー操作が未限定

CfnExec2Dataの `OpenSearchServerlessPoliciesNoResourceLevelSupport` は、アクセス・セキュリティポリシーの作成・変更・削除をResource `*`、条件なしで許可している。他システムのポリシーにも及ぶため、今回の権限限定方針に対して修正が必要。

Resource `*` 自体はAPIの制約上必要。セキュリティポリシー操作とアクセス・ポリシー操作を分け、`aoss:collection` で `stg01-demo-scholarship-kb` に限定する。アクセス・ポリシーではインデックス側も別途 `aoss:index` により対象範囲を限定する。コレクション条件だけではインデックス規則を制限できない。

実テンプレートの対象規則：
- collection/stg01-demo-scholarship-kb
- dashboard/stg01-demo-scholarship-kb（ネットワークポリシー）
- index/stg01-demo-scholarship-kb/*（データアクセス・ポリシー）

条件付きポリシーの確定時には、対象コレクションだけ・対象インデックスだけ・対象と他システムが混在する規則・対象外だけの規則について許可/拒否を確認する。単純な条件追加だけで全ケースを保証したとしない。

### コレクション作成・タグ権限のResource指定

同ポリシーの `aoss:CreateCollection` はcollection ARNを指定しているが、AWSのサービス認可表ではリソース単位の指定に非対応。`aoss:TagResource` / `aoss:UntagResource` も同様。現行の指定は必要時に許可として働かない。

今回のBoundary・Retain変更にコレクション新規作成は含まれない。常設権限を無条件のResource `*` に広げず、今後の新規作成・タグ変更の際に必要な権限を事前調整する扱いを推奨。常設する場合は対応するタグ条件とCDK側タグの整合を別途設計する。現時点でタグが付いているとは仮定していない。

## 初回移行の注意

CfnExec1InfraにはDeleteRolePermissionsBoundaryの明示的Denyがある。これは権限境界の解除防止として維持する。初回付与と同じ更新で別の処理が失敗し、以前の「Boundaryなし」へロールバックしようとすると、このDenyにより復旧が止まる可能性がある。
失敗時に安易にDenyを解除せず、CloudFormationイベントから対象を確認し、Boundaryを保持した復旧をH+さんの管理権限で行う。通常のアプリ変更とは分けて反映する。

## 進行順序

1. 本資料の権限修正をH+さん側ポリシーへ反映。
2. アプリ側のBoundary・Retainコミット準備完了を連絡。
3. H+さんがbootstrapを更新し、完了を連絡。
4. その後に対象コミットをPushし、自動デプロイを確認。
5. Retain反映を確認してexternalへ変更・反映。
6. チャット、ファイル取込、KB取り込みを含む実動作確認。

同時刻である必要はなく、bootstrap更新完了→デプロイの順番を守る。バックアップ作業とは別件。

## 根拠

- AWSサービス認可表（AOSS）: https://docs.aws.amazon.com/service-authorization/latest/reference/list_opensearchserverless.html
- 条件キーとコレクション/インデックスの違い: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/security-iam-serverless.html

## 確認範囲の限界

EC2のバックアップ用ロールからIAMの実アタッチ状態は参照できないため、共有JSONを根拠としている。全サービスのすべての作成・削除・置換経路の許可を保証するものではない。仮lookupによる構造試験のテンプレートはデプロイに使用しない。
