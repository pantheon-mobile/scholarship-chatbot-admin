# H+さん検証環境：2026年9月28日のバックアップへの復元手順

## 対象

- AWSアカウント：796575284584、東京リージョン。
- スタック：ScholarshipChatbot-stg01-demo。
- 復元基準：2026年9月28日20:23頃（日本時間）。
- 保存先：s3://gakupita.backup/ai-chatbot/stg01-demo/20260928T111648Z/
- 実行場所：35.75.92.3 のEC2へ pms01 でSSH接続。
- スクリプト：/home/pms01/ai-chatbot-backup/scripts/
- Python：/home/pms01/ai-chatbot-backup/venv/bin/python

H+さん自身で実行する際の手順です。DB全体・登録ファイル等を基準時点へ戻すため、基準以降の追加・変更・削除も巻き戻ります。共用ALB・GAKUPITA・CPFは停止しません。

## 作業前

- 検証環境の利用、デプロイ、手動学習、DB直接編集、資料S3への直接書き込みを止めてください。
- 復元元は183日保持のため、保存先に存在することを確認してください。
- コード・タスク定義・DB構造・検索設定が保存時点から変わっている場合、先に弊社へご相談ください。構成不一致を無視して実行しないでください。
- 定期学習は毎日01:00（日本時間）、起動要求の再試行は最大2時間です。01:00〜03:00や実行中の学習がある場合は完了を待ってください。スケジュールを変更した場合は、その設定で改めて確認してください。
- 正式なCPFログインを使った確認を行える方を用意してください。

以下はEC2にSSH接続後、同じbashセッションで順番に実行します。sudoは不要です。エラー時は後続の操作を行わず、表示内容を弊社へ共有してください。

## 1. 作業領域と認証の確認

```bash
bash
set -Eeuo pipefail
umask 077
BASELINE_PYTHON=/home/pms01/ai-chatbot-backup/venv/bin/python
SCRIPT_ROOT=/home/pms01/ai-chatbot-backup/scripts
RESTORE_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RESTORE_ROOT="/home/pms01/ai-chatbot-backup/manual-restores/$RESTORE_RUN_ID"
mkdir -p "$RESTORE_ROOT"
chmod 700 "$RESTORE_ROOT"
aws sts get-caller-identity
"$BASELINE_PYTHON" "$SCRIPT_ROOT/preflight-validation-baseline.py" \
  --work-directory "$RESTORE_ROOT" > "$RESTORE_ROOT/preflight.json"
```

アカウントが796575284584、実行ロールがdev-gakupita-app-build-server-roleであることを確認します。別のAWS認証情報で実行しないでください。スクリプト側にもアカウント・スタックの確認があります。

## 2. 復元元を取得し検証

```bash
aws s3 cp \
  s3://gakupita.backup/ai-chatbot/stg01-demo/20260928T111648Z/ \
  "$RESTORE_ROOT/baseline/" --recursive --only-show-errors
"$BASELINE_PYTHON" "$SCRIPT_ROOT/validation_baseline.py" verify \
  --directory "$RESTORE_ROOT/baseline"
```

`Backup checksums OK` を確認してください。異常がある場合は停止操作へ進みません。

## 3. チャットボットと定期学習を停止

```bash
"$BASELINE_PYTHON" "$SCRIPT_ROOT/validation_maintenance.py" pause \
  --state "$RESTORE_ROOT/pause.json"
```

停止前の台数・タスク定義・定期学習の状態がpause.jsonに保存されます。停止要求が出ても実際の終了まで数分かかります。待機中に強制終了せず、Pausedの表示まで待ってください。追加のDB接続ツールも切断してください。

## 4. 復元

```bash
BASELINE_PYTHON="$BASELINE_PYTHON" \
  bash "$SCRIPT_ROOT/restore-validation-baseline.sh" \
  --directory "$RESTORE_ROOT/baseline" \
  --emergency-directory "$RESTORE_ROOT/before-restore" \
  --confirm '796575284584/ScholarshipChatbot-stg01-demo'
```

以下を順に実施します。

1. 保存データ・環境構成・停止状態を確認。
2. 復元直前のDB・S3をbefore-restoreへ退避。退避失敗時は復元を開始しません。
3. DB全体を復元。
4. 登録ファイル等を復元し、基準にない追加ファイルを削除。
5. DB件数・S3の全ファイル内容を照合。
6. 5つのBedrockデータソースを同期。Web再取得・原本の再変換はしません。

`Restore verified` と `before-restore/restore-result.json` の作成を確認します。復元スクリプトはサービスを自動再開しません。

エラー時は部分的な復元状態の可能性があるため、サービスを再開しないでください。before-restoreを削除せず、エラーと作業領域のパスを弊社へ共有してください。同じ退避先に上書きしてやり直さないでください。

## 5. アプリを再開して確認

```bash
"$BASELINE_PYTHON" "$SCRIPT_ROOT/validation_maintenance.py" start-app \
  --state "$RESTORE_ROOT/pause.json"
```

正式なCPFログインで以下を確認します。

- FAQ・データソース・カテゴリ等が基準の状態になっている。
- FAQ・資料を根拠とする質問に回答できる。
- 参照元リンクからファイルを取得できる。
- 基準以降に追加したデータが残っていない。

基準時点の目安はFAQ2,213件、データソース179件、カテゴリ20件です。ログインや操作を行うと、新しい履歴・ログは正常に追加されます。

## 6. 定期学習を再開

```bash
"$BASELINE_PYTHON" "$SCRIPT_ROOT/validation_maintenance.py" resume-schedule \
  --state "$RESTORE_ROOT/pause.json"
```

停止前の有効・無効状態へ戻ります。学習が再開するとWebの取得内容等が更新される場合があるため、基準状態での確認を先に済ませてください。

## 7. 記録と作業用データの扱い

作業日時、復元元、restore-result.json、確認結果を保管してください。before-restoreは復元直前の重要な退避データです。復元の受入確認と必要な退避先への保管が済むまで削除しないでください。共用EC2上に個人情報を含むコピーを無期限に残さず、確認後に作業領域の扱いを決めてください。

今回の手順はAWS設定やCloudWatchのログ、S3の過去バージョンを過去へ戻すものではありません。時間経過で期限切れになったセッションは再ログインが必要です。
