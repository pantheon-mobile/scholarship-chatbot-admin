# 客先検証環境：「今」の全データを保存・復元する

## 対象と方針

- 対象AWSアカウント：`796575284584`、東京リージョン。
- 対象スタック：`ScholarshipChatbot-stg01-demo`。本番・自社環境では動かないよう固定している。
- PostgreSQL `scholarship` **データベース全体**（FAQ、カテゴリ・種別、データソース、ユーザー、セッション、履歴、操作ログ、ジョブ、設定、シーケンスなど）を保存する。
- スタック所有の `DocumentsBucketName` バケットの**全現行オブジェクト**を保存する。原本・学習用文書・メタデータ・Web取得記録を含む。共有バケットは拒否する。
- 復元時はDBを削除・再作成し、S3に後から追加されたファイルも除去する。バケットそのもの、過去バージョン、バケット設定は削除しない。
- 保存済みの学習用文書からBedrockを直接同期する。アプリの「今すぐ実行」は使わない。Webの再取得・ファイル再変換はしない。
- コード・タスク定義・検索先等が変わっていない前提。タスク定義等の相違は停止する。相違を無視するオプションは用意しない。
- CloudWatchログ、AWSの監査ログ、Secrets Manager、DBのクラスタ共通ロール、AWS設定は巻き戻さない。時計も戻らないため、保存したセッションの期限が過ぎていれば再ログインが必要。
- 回答文の完全一致や、検索インデックスの内部表現の完全一致を保証するものではない。

**作成しただけではバックアップは存在しない。実際に停止して保存した時点が復元基準になる。**

## ファイル

- `infrastructure/scripts/validation_baseline.py`：参照、保存、検証、復元。
- `infrastructure/scripts/preflight-validation-baseline.py`：停止前に実行する読取専用の接続・ツール・容量・保存先設定確認。
- `infrastructure/scripts/save-validation-baseline.sh`：保存の入口。
- `infrastructure/scripts/restore-validation-baseline.sh`：復元の入口。
- `infrastructure/scripts/validation_maintenance.py`：アプリと定期実行の停止・再開。

バックアップは実行端末の指定ディレクトリに作成する。`database.dump`、連番のオブジェクト本体、元のS3キー・属性・ハッシュ等を記録した `manifest.json` の組である。S3キーをローカルパスに使わないため、特殊文字や `../` を含むキーでも安全に保存できる。

## 2026-09-25 客先と合意した実行場所・保存先

- 作業場所：GAKUPITA/CPF共用のビルド／デプロイ用EC2。接続ユーザー・接続鍵等は客先準備待ち。既存ビルドやデプロイと作業時間を調整する。
- EC2のIAMロール：`dev-gakupita-app-build-server-role`。通常はEC2のインスタンスロールを使うため、新しいアクセスキーは不要。初期構築はCDKロールへのAssumeRoleを経由するため、バックアップの直接操作権限が付与済みとは判断しない。不足するAPI許可は対象リソースを限定して依頼する。
- 保存先：`s3://gakupita.backup/ai-chatbot/stg01-demo/<取得日時>/`。GAKUPITA共用のバックアップバケット内の専用prefix。**このバケットは退避先であり、復元による削除・同期の対象にしない。** 他システムのprefixへ書き込まない。
- 保持：客先の既存ライフサイクルに従い183日。実際の対象prefixへの適用、現行版・過去バージョンの扱いを接続後に確認し、既存ルールを変更しない。長期間使う復元基準では、期限前に再取得等の判断が必要。
- 共用EC2全体のIAMロール変更・sudoers変更はこのスクリプトでは行わない。通常実行にsudoは不要。Python/PostgreSQLクライアント等の導入が必要なら客先と調整する。
- 保存・復元で停止するのはAIチャットボットの対象環境だけ。GAKUPITA/CPFや共用ALBを停止しない。

### 接続後、停止前に実行する事前確認

必要ツールは下記の実行前準備に従って用意し、作業用の非公開ディレクトリを作成する。EC2の暗号化ディスク・アクセス権限・空き容量も確認する。

```bash
export BASELINE_PYTHON="<バックアップ用venv>/bin/python"
export BASELINE_ROOT="$HOME/validation-backups"
mkdir -p "$BASELINE_ROOT"
chmod 700 "$BASELINE_ROOT"
# 作業シェルに別のAWS_PROFILE/アクセスキーが残っていないことを確認。
# --profile未指定でEC2ロールを利用する。認証情報の値を出力しない。
"$BASELINE_PYTHON" infrastructure/scripts/preflight-validation-baseline.py \
  --work-directory "$BASELINE_ROOT" > "$BASELINE_ROOT/preflight.json"
```

出力のアカウントは796575284584、呼出元はdev-gakupita-app-build-server-roleであることを確認する。異なるロールが表示されたら原因を確認してから進める。S3の設定取得がAccessDenied等の場合は確認未完了として扱う。`preflight.json` は環境識別子を含むため公開しない。

このコマンドはDBを読み取り専用で照会し、ECSやS3の状態を読むだけで、停止・ダンプ・S3書込み・復元を行わない。PGツールのメジャーバージョン一致と空き容量を確認する。容量見積りにはダンプ一時領域や復元直前退避分の余裕が別途必要。

**この事前確認の成功だけでは、PutObject/KMS暗号化・復号、ECS/Scheduler更新、iam:PassRole、復元時のDB作成権限等を確認したことにはならない。** 下記権限一覧と実ポリシーを照合し、必要な場合は専用prefixでの小さなアップロード／ダウンロード試験等を作業計画に追加する。読取検査中に試験書込みを自動実行しない。保守時間が決まるまではpause/save/restoreを実行しない。

客先への接続準備が完了したら、インスタンスID・接続方法・接続ユーザーの案内を受ける。秘密鍵・アクセスキー・DBパスワードをGitや手順書に記載しない。

## 実行前の準備

客先でAWS操作権限があり、RDSへ接続できる運用端末／踏み台で実行する。Codex側に客先権限がなくても、担当者にこの手順とスクリプトを渡せる。

1. Python 3.11以上、`boto3`、`psycopg[binary]` を用意する。既存のbackend用venvも利用可能。専用venvの場合は `python -m pip install -r infrastructure/scripts/requirements-baseline.txt` で導入する。
2. PostgreSQLサーバーと同じメジャーバージョンの `pg_dump` / `pg_restore` をPATHに入れる。
3. 共用EC2では既存のIAMロールを利用する（--profile省略）。別端末・SSM利用の場合は客先用AWSプロファイルを設定する。アクセスキーやDBパスワードをスクリプトや手順書へ記載しない。
4. RDSへの経路とセキュリティグループの接続許可を確認する。RDSを公開したり、`0.0.0.0/0` を許可したりしない。
5. 端末の暗号化された保存領域に、DB＋S3全量を格納できる空きを用意する。復元時は追加で直前退避分が必要。
6. 保存先と保持期間は担当者が決める。バックアップに個人情報・セッション情報等が含まれるため、Gitや公開ストレージへ置かない。
7. コード変更・デプロイ・手動RunTask・他のS3/DB書込みを作業中禁止する。CDKの再デプロイや自動スケーリングでサービスが再起動しないようにする。
8. 保存前にFAQ回答と資料検索が正常で、管理画面の「学習中」や実行中ジョブがないことを確認する。準備中のデータをそのまま保存することもできるが、未学習の状態も復元される。

必要権限（対象リソースに限定して付与）：

- STS `GetCallerIdentity`、CloudFormation `DescribeStacks`, `ListStackResources`
- ECS `DescribeServices`, `DescribeTaskDefinition`, `ListTasks`, `UpdateService`
- Scheduler `GetSchedule`, `UpdateSchedule`、更新で必要な対象ロールの `iam:PassRole`
- Secrets Manager `GetSecretValue`（スタックのDBシークレットのみ）と必要なKMS復号権限
- S3 `ListBucket`, `GetObject`, `GetObjectVersion`, `GetObjectTagging`, `GetObjectVersionTagging`, `PutObject`, `PutObjectTagging`, `DeleteObject`、マルチパートアップロード関連、必要なKMS権限
- Bedrock `GetDataSource`, `ListIngestionJobs`, `StartIngestionJob`, `GetIngestionJob`
- DB所有者としてダンプ・DB削除／作成・復元を実行できる権限。実際にはスタックのDB管理者シークレットを使用する。

### バックアップ先の追加権限と共用領域の扱い

退避先gakupita.backupには、専用prefixのListBucket・GetObject・PutObject、必要なマルチパート操作とKMS権限が必要。これは復元対象のDocumentsBucketとは別権限として整理する。退避先全体へのDeleteObjectやバケット削除権限は要求しない。試験データを削除する場合も専用の試験キーだけに限定する。

事前確認ではGetLifecycleConfiguration・GetEncryptionConfiguration・GetBucketVersioningも参照する。許可できない項目は客先の設定情報で確認する。書込時のKMSキー指定等がバケットポリシーで要求される場合は、実設定を確認して転送コマンドを調整する。共有バケットへのsync --deleteやバケット全体の設定変更は行わない。

## 接続・保存先の設定例

以下はリポジトリのルートで実行する。共用EC2ではAWS_PROFILEの指定は不要。別端末でプロファイルを使う場合だけ、確認した客先用の名前を指定する。パスは例であり、保存先を作業者が選ぶ。

```bash
export BASELINE_PYTHON="$PWD/.venv/bin/python"
# EC2のインスタンスロールを使う場合、AWS_PROFILEは指定しない。
export BASELINE_ROOT="$HOME/validation-backups"
mkdir -p "$BASELINE_ROOT"
chmod 700 "$BASELINE_ROOT"
"$BASELINE_PYTHON" infrastructure/scripts/validation_baseline.py inspect
```

`inspect` のアカウント、スタック、バケット、DBホストを確認する。秘密値は出力しない。スクリプトがSecrets Managerからパスワードを読み、子プロセスの環境変数でPostgreSQLツールに渡す。パスワードをコマンド引数やファイルには書かない。

RDSはプライベート配置のため、通常の端末から直接接続できない場合がある。既存の踏み台からSSMポート転送する場合は、確認したRDSエンドポイントを転送先にする。例：

```bash
aws ssm start-session --target '<客先のSSM管理対象踏み台ID>' \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["<inspectで確認したRDSホスト>"],"portNumber":["5432"],"localPortNumber":["15432"]}'
```

別ターミナルで保存・復元コマンドに `--db-host 127.0.0.1 --db-port 15432` を加える。踏み台IDは現環境で確認が必要であり、本手順では仮定しない。専用の運用端末からRDSへ直接接続できる場合はこの追加引数は不要。

## A. 基準状態の保存

### 1. メンテナンスへ移行

利用者へ停止を案内し、新規操作を止め、処理中の操作の完了を確認する。

```bash
"$BASELINE_PYTHON" infrastructure/scripts/validation_maintenance.py pause \
  --state "$BASELINE_ROOT/baseline-pause.json"
```

この処理はスケジュールを無効化し、フロントエンドとバックエンドを0台にする。表示は503等になる場合がある。専用メンテナンス画面は追加しない。ワーカーを強制終了せず、クラスタ内のタスクの終了を最大2時間待つ。停止前の台数とスケジュールの有効状態はJSONに保存する。失敗しても勝手に再開しない。

**Schedulerを無効化しても、既に配信中／再試行中の起動要求を取り消せるとは限らない。** 現在の構成は最大イベント経過時間2時間である。直前の起動・再試行が残っていないことを運用ログで確認する。確認できない場合は無効化から2時間以上待ち、起動済みワーカーの終了も確認する。DLQの再投入は作業中禁止する。別のスケジュール／外部連携が同じDB・S3に書き込む場合も停止する。

他のDB接続ツールを切断する。スクリプトはECSタスク・サービス・Scheduler・Bedrock処理・他のDB接続が残っていれば保存を拒否する。強制停止によりDB内に「学習中」「RUNNING」等が残った場合は、基準として保存する前に原因を解消する。

### 2. 保存

```bash
bash infrastructure/scripts/save-validation-baseline.sh \
  --directory "$BASELINE_ROOT/baseline-20260917"
```

SSMの場合は接続用引数も追加する。既存ディレクトリへの上書きは拒否する。保存中にS3一覧等が変化した場合も失敗する。`manifest.json` がない、または `complete` がtrueでないセットは復元できない。

```bash
"$BASELINE_PYTHON" infrastructure/scripts/validation_baseline.py verify \
  --directory "$BASELINE_ROOT/baseline-20260917"
```

検証は全ファイルのSHA-256を照合する（AWS接続不要）。これは破損検査であり、実際の復元リハーサルの代わりではない。

保存ディレクトリ一式を合意済みの共用バックアップバケット内の専用prefixへ複製する。以下の取得日時・ローカルディレクトリは実際の保存セットに合わせる。同じprefixを再利用しない。先に全データを転送し、最後にmanifest.jsonを転送する。

```bash
aws s3 cp "$BASELINE_ROOT/baseline-20260917/" \
  's3://gakupita.backup/ai-chatbot/stg01-demo/20260917T000000Z/' \
  --recursive --exclude 'manifest.json' --only-show-errors
# 上の転送が成功したことを確認してから実行する。
aws s3 cp "$BASELINE_ROOT/baseline-20260917/manifest.json" \
  's3://gakupita.backup/ai-chatbot/stg01-demo/20260917T000000Z/manifest.json' \
  --only-show-errors
```

**DocumentsBucketNameバケットへは保管しない。** バックアップを検索対象に含めたり、復元時に一緒に消したりしないため。保存先は既存の183日保持を使用する。183日を超えて必要な場合は事前に運用を調整する。共用バケットのライフサイクルを無断で変更しない。ダウンロードしたコピーも `verify` で確認する。取得完了を担当者が記録し、元の保存セットを書き換えない。

### 3. 検証を再開

```bash
"$BASELINE_PYTHON" infrastructure/scripts/validation_maintenance.py start-app \
  --state "$BASELINE_ROOT/baseline-pause.json"
```

通常のCPFでログインし、画面・FAQ・資料検索・参照元を確認する。その後、元の定期実行状態に戻す。

```bash
"$BASELINE_PYTHON" infrastructure/scripts/validation_maintenance.py resume-schedule \
  --state "$BASELINE_ROOT/baseline-pause.json"
```

## B. 10日後に全データを戻す

### 1. 保存セットと実行環境を確認

バックアップを運用端末へ取得して `verify` を実行する。必要なPostgreSQLツールを用意し、コード・DB構造・検索設定が変わっていないことを確認する。アプリの起動時にAlembicが実行されるため、コード変更がある場合にはこの手順をそのまま使わない。

新しい停止状態ファイルで `pause` を実行し、Aと同様に起動要求・ワーカー・DB接続・Bedrockジョブを止める。

```bash
"$BASELINE_PYTHON" infrastructure/scripts/validation_maintenance.py pause \
  --state "$BASELINE_ROOT/restore-pause.json"
```

### 2. 復元

```bash
bash infrastructure/scripts/restore-validation-baseline.sh \
  --directory "$BASELINE_ROOT/baseline-20260917" \
  --emergency-directory "$BASELINE_ROOT/before-restore-20260927" \
  --confirm '796575284584/ScholarshipChatbot-stg01-demo'
```

SSMの場合は接続用引数も追加する。復元は次の順で進む。

1. アカウント・スタック・S3・DB・検索設定・タスク定義と、保存ファイルのハッシュを照合。
2. 停止状態を確認。
3. **復元直前のDB・S3を必ず退避**。退避に失敗したら変更を開始しない。
4. `pg_restore --clean --create` でDB全体を削除・再作成して復元。
5. S3の全保存オブジェクトを戻し、保存セットに存在しない現行キーを削除。内容・メタデータ・Content-Type・タグ等を復元する。暗号化には現在のバケット既定設定を使い、S3バージョンID・最終更新日時は巻き戻さない。
6. テーブル件数、S3キー一覧、S3全内容のSHA-256を検査。
7. 形式別のBedrockデータソースを順次直接同期。失敗文書数が0でない場合も失敗扱い。
8. 直前退避ディレクトリに `restore-result.json` を作成。アプリと定期実行は停止のまま。

**AWS全体の一括トランザクションではないため、中断時はDBとS3が途中状態になる可能性がある。エラー時に再開しない。** エラー原因を解消して、基準セットから同じ手順を再実行する。退避先は毎回別名にする。正常だった直前状態に戻す場合は、最初の直前退避セットを復元元に指定する。DB自体がなくなった等で再実行の退避が取れない場合は、保存済みの直前退避を保持し、DB管理者が復旧する（自動的なチェック回避はしない）。

### 3. アプリのみ再開し、受入確認

```bash
"$BASELINE_PYTHON" infrastructure/scripts/validation_maintenance.py start-app \
  --state "$BASELINE_ROOT/restore-pause.json"
```

確認項目：

- FAQ・データソース・カテゴリ・種別・ユーザー・履歴が基準状態に戻っている。
- 基準に存在したFAQと資料を根拠とする質問へ回答できる。
- 復元後に残すべきでない、検証中に追加した資料が検索結果／回答根拠に出ない。
- 参照元リンクから当時の原本が取得できる。
- 基準時点のWeb本文が検索対象になっている。
- Bedrock同期の失敗がなく、各データソースの同期結果が記録されている。

通常のログイン・確認を行うと、その分の履歴等が新しく作成される。「復元処理完了時点」を基準とし、利用再開後の新しい更新は正常動作として扱う。

確認後、必要なタイミングで `resume-schedule --state "$BASELINE_ROOT/restore-pause.json"` を実行する。再開するとWeb自動再取得等が新しい内容へ更新する可能性がある。**復元した内容を使った検証を先に行う場合は、その検証が終わるまでスケジュールを無効のままにする。** これは一時停止であり、コードやAWS構成を過去へ巻き戻す操作ではない。

## 検証状況と制限

ローカルの自動テストで、破損検出、環境違いの拒否、直前退避失敗時の停止、追加S3キーの削除、同期失敗時の停止、Scheduler設定の保持を確認済み。さらにローカルPostgreSQL 16の使い捨てDBで実際にダンプ・復元を行い、更新行の復旧、後から追加した行・テーブルの除去、シーケンスの復元を確認済み。AWS部分は模擬しており、ローカルの既存アプリDBは変更していない。2026-09-25には自社AWSの隔離環境でも実RDS・S3・Bedrockの保存／復元試験を実施した（下記参照）。客先固有のIAM・KMS・RDS経路・実データ量での所要時間は客先での確認が必要。スクリプトの提供はバックアップ取得／AWSでの復元完了を意味しない。

参考：

- [PostgreSQL pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- [PostgreSQL pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)
- [Bedrock S3データソースの同期](https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html)
- [Scheduler UpdateSchedule：省略すると既定値になるため既存設定を保持](https://docs.aws.amazon.com/scheduler/latest/APIReference/API_UpdateSchedule.html)

### 2026-09-25 事前確認ツールの追加検証

既存の保存・復元の安全性テストと追加した事前確認テストは計15件成功。事前確認のS3操作が読取のみであること、設定取得権限不足を確認済みにしないこと、退避先を保存元として使わないこと、PostgreSQLクライアントの版不一致を拒否することを模擬環境で確認した。CLIのヘルプ表示も確認済み。客先EC2接続、実IAM権限、実DB接続、実S3への転送、バックアップ取得は未実施。接続準備と保守時間の調整を待つ。

### 2026-09-25 自社AWSでの隔離試験

自社の稼働中開発環境とは別に、一時スタック `ScholarshipChatbot-backup-rehearsal` を作成し、実際のRDS PostgreSQL 16・S3・Bedrock Knowledge Base／OpenSearch Serverlessで試験した。稼働中の開発環境のDB・S3・サービスは変更していない。

- アプリのマイグレーションで初期化した22テーブルを対象に、FAQ、カテゴリ、種別、ファイル／Webデータソース、利用者・認証情報、チャット履歴、評価、ログのテストデータを使用。
- 保存後に行の更新・削除・追加とテーブル追加を行い、復元後の全テーブルの内容・件数・シーケンス値が保存時点と一致することを確認。
- 原本、学習用本文、メタデータの計4 S3オブジェクトを保存し、別のバックアップ用S3バケットへ転送・再取得してハッシュを照合。
- S3の上書き・削除・追加を復元し、内容、メタデータ、Content-Type、Cache-Control、タグを照合。
- Bedrockの同期後、保存時点の本文が検索され、保存後に変更・追加した本文が検索されないことを実際のRetrieve APIで確認。
- 破損したDBダンプは復元開始前に拒否。正常な復元では直前退避も取得。
- テスト用ECSサービスの停止・再開、元の無効状態へのScheduler復帰、再開後のバックエンド `/api/v1/health`（DB接続あり）を確認。

実AWSでS3の `StreamingBody` のコンテキスト管理に起因する読取エラーを検出し、SDKのストリームを保持したまま確実に閉じる方式に修正した。実SDKクラスを使った回帰試験を追加し、ローカルの実PostgreSQL復元を含む18テストが成功した。

自社試験専用の引数は `--target self-test`。アカウント、スタック名、Purposeタグ、DB・S3・KB・ECSの所有関係を確認する。任意のスタックや稼働中の開発環境への切替用引数ではない。**客先での通常作業ではこの引数を指定しない**（既定の客先固定対象を使用する）。

詳細は [AWS保存・復元試験結果](validation-baseline-aws-rehearsal-20260925.md) を参照。客先バックアップ取得、客先IAMでの実行、実際のチャット画面による受入確認は未実施。
