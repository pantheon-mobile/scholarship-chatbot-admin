FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
COPY pyproject.toml ./pyproject.toml

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
