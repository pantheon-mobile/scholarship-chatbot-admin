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
- 実ファイル保存・ダウンロード、Web取得・再学習、Knowledge Base同期、認証・認可、CB-203～CB-206本画面は未実装です。
