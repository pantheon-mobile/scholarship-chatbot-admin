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
