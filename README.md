# Scholarship Chatbot Admin

This repository contains a minimal local development setup for a scholarship chatbot admin site.

## Architecture

- frontend: Next.js + TypeScript + App Router
- backend: FastAPI + Python 3.12
- database: PostgreSQL
- ORM: SQLAlchemy 2
- migrations: Alembic
- orchestration: Docker Compose

## Local development

1. Copy `.env.example` to `.env` if you need environment variables locally.
2. Run:

```bash
docker compose up --build
```

3. Open the frontend in your browser:

- `http://localhost:3000`

4. The frontend calls the backend health endpoint at `/api/v1/health`.

## Project structure

- `frontend/` - Next.js app
- `backend/` - FastAPI app and database config
- `compose.yaml` - Docker Compose definition

## Tests

- Frontend build and lint are exercised in CI
- Backend tests are executed with `pytest`

## Notes

- Do not commit `.env`
- The backend connects to PostgreSQL using `DATABASE_URL`
- Alembic is configured for future schema migrations
- CB-207の種別1～3の正式な初期値は資料上で未確定です。現在の初期値は維持し、業務担当者の確認後に別途更新します。

## CB-202 MVP decisions

- 検索条件はすべてANDで結合し、キーワードだけはタイトル・ファイル名・URLをOR部分一致で検索します。
- カテゴリの正式マスタは未確定のため、MVPでは`data_sources.category_name`をNULL可の暫定表示列として持ち、検索選択肢は「すべて」のみです。
- ページ直接移動は、項目定義書と画面画像の差を解消するMVP判断として数値入力欄を使用します。範囲外は`PAGE_NOT_FOUND`で共通Modalを表示します。
- 回答ソースが無効でも参照リンクの表示／非表示は変更できます。両トグルは確認なしで即時保存し、楽観ロックを使用します。
- 削除はMVPでは物理削除です。行削除・一括削除とも確認Modalを表示し、一括削除は全件を同一トランザクションで処理します。
- 一覧Excelは検索結果の確認用であり、未確定の一括更新用フォーマットではありません。一括更新機能はMVP対象外です。
- `data_source_classification_values`は既存CB-207テーブルへの複合一意制約追加を避け、単純な外部キーで構成します。種別値が指定種別に属することは`DataSourceService.validate_classification_assignments`で必ず検証します。
- 0002の12件は画面動作確認用サンプルです。`source_type`と`［サンプル］`付きtitleで冪等判定するMVP用seedであり、正式データ投入時に廃止または見直します。
- 実ファイルダウンロード、Web取得・再学習、Knowledge Base同期、認証・認可は未実装です。

## CB-203 local file upload MVP

- MVPの実ファイルは`UPLOAD_DIR`（Docker Composeでは`/app/storage/uploads`）へ保存し、named volumeでコンテナ再起動後も保持します。ストレージ処理はAdapterへ分離し、将来S3 Adapterへ交換できる構成です。
- 新規登録時の状態は`PREPARING`です。Bedrock Knowledge Base同期と`PREPARING`以降の自動状態遷移は実装していません。
- 正式カテゴリは未実装のため、CB-203ではカテゴリを選択できず、`category_name`は常にNULLです。
- 既存データソースと同じ元ファイル名でも別データソースとして新規登録します。UUIDベースの`storage_key`により保存済みファイルを上書きしません。
- タイトルを省略した場合は拡張子を含む元ファイル名を登録します。複数ファイルでは個別の元ファイル名をタイトルにします。
- 複数ファイル登録は全件成功または全件失敗です。失敗時はDBをロールバックし、そのリクエストで保存した一時ファイル・確定ファイルを削除します。
- 拡張子、Content-Type、基本シグネチャ、件数、合計容量、0バイト、同一リクエスト内の同名を検証します。正式なウイルススキャンは未実装です。
- 登録内容はseedではなくユーザー登録データとして`data_sources`、`data_source_files`、`data_source_classification_values`へ保存します。

## CB-204 file attribute edit MVP

- CB-204は既存FILEデータソースの属性編集のみを行い、ファイル差し替え、再アップロード、`file_name`、`storage_key`、`mime_type`、`size_bytes`の変更は行いません。Storage Adapterも使用しません。
- タイトルが空文字または空白のみの場合は、CB-203と同様に既存のファイル名をタイトルとして保存します。
- 正式カテゴリ機能は未実装のため、`category_name`は現在値をdisabled表示するだけで更新対象に含めません。
- dirty状態は入力操作の有無ではなく、タイトル、種別1～3、優先度、回答ソース、参照リンクの初期値との差分で判定します。差分がない場合は更新ボタンを無効化します。
- 属性更新では現在の`status`を維持し、Bedrock同期・再学習を行いません。更新対象と種別関連、`version`、`updated_at`だけを1トランザクションで更新します。

## CB-205 website URL registration MVP

- CB-205は1件のURLと任意タイトルを登録するMVPです。デザイン資料にある複数URL入力、ファイル一括入力、フォーマットダウンロードは実装しません。
- URLは`http`または`https`の絶対URLだけを許可し、文字列形式のみ検証します。DNS、到達可否、HTTP応答、SSL、リダイレクト、robots.txt、ページ内容は確認しません。
- URL上限は、タイトル省略時にURL全体を`data_sources.title(500)`へ保存できるよう500文字とします。タイトルが空文字または空白のみの場合は、登録URLをそのままタイトルとして保存します。
- 同じURLが既に存在しても、自動更新・重複排除は行わず別データソースとして新規登録します。
- 正式カテゴリ機能は未実装のため、カテゴリはdisabled表示し、`category_name`はNULLで登録します。
- 登録時は`source_type=WEB`、`format=Web`、`status=PREPARING`、`size_bytes=NULL`、`character_count=NULL`、`last_fetched_at=NULL`、`version=1`です。
- Web取得、スクレイピング、本文抽出、Bedrock同期、再学習、ingestion jobは実行せず、`PREPARING`以降の自動状態遷移も行いません。

## CB-206 website attribute edit MVP

- CB-206は登録済みWEBデータソースのURLと属性を編集します。デザイン資料ではカテゴリが選択可能に見えますが、正式カテゴリ機能が未実装のため現在値をdisabled表示し、`category_name`を更新しません。
- URLは変更できますが、Web取得、到達確認、スクレイピング、Bedrock同期、再学習は行いません。
- URL変更時も現在の`status`、`last_fetched_at`、`character_count`を維持し、`PREPARING`へ戻しません。
- タイトルが空文字または空白のみの場合は、更新後のURLをタイトルとして保存します。他のデータソースと同じURLへの更新も許可します。
- dirty状態はURL、タイトル、種別1～3、優先度、回答ソース、参照リンクの初期値との差分で判定し、差分がない場合またはURLが空の場合は更新ボタンを無効化します。

## CB-213 category list MVP

- CB-213では`categories`マスタだけを正式化します。`data_sources`との正式な関連は、1データソース1カテゴリか複数カテゴリかの仕様確定後に別migrationで対応します。
- 暫定列`data_sources.category_name`は維持し、`category_id`や中間テーブルの追加、既存文字列の自動移行、CB-202～206へのカテゴリ選択機能の横展開は行いません。
- 使用中カテゴリの判定は未実装です。カテゴリ削除はMVPでは物理削除で、選択したカテゴリの全子孫も同一トランザクションで削除します。`category_name`は変更しません。
- カテゴリは単一親の任意階層ツリーです。最大階層数は設けず、同一親配下（ルート同士を含む）の同名を禁止し、異なる親配下の同名は許可します。カテゴリ名は前後空白を除去した値を前提とします。
- 初期表示は全展開で、展開状態は保存しません。デザイン画像だけにある親カテゴリ絞り込みは、20260811版の画面項目定義にないため実装しません。ページング、検索、列ソートもMVP対象外です。
- D&Dは同一親配下の兄弟間だけ許可し、ドロップ時に即時保存します。異なる親への移動とD&Dによる親変更は行いません。
- 正式な初期カテゴリ値が資料にないためseedは投入しません。画像中のカテゴリ値は表示例として扱います。
- CB-214（カテゴリ新規追加）とCB-215（カテゴリ編集）は独立ページではなく、CB-213の一覧上で共通Modalを使って操作します。新規追加は1カテゴリずつ行い、カテゴリ名は前後空白を除去した1～15文字です。
- `parent_id=NULL`は第一階層を表します。新規カテゴリは同一親配下の末尾へ追加し、同一親配下（ルート同士を含む）の同名は禁止、異なる親配下の同名は許可します。
- 編集ではカテゴリ名と親カテゴリを変更できます。自分自身または子孫を親にすることは禁止し、親変更時はサブツリーを維持したまま新しい親配下の末尾へ移動し、旧親配下の表示順を詰めます。
- 編集は`version`による楽観ロックを使用します。既存の`data_sources.category_name`とカテゴリマスタの正式な関連は引き続き未実装です。
