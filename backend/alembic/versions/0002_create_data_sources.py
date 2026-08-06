"""create data source tables and MVP sample data

Revision ID: 0002_cb202
Revises: 0001_cb207
Create Date: 2026-08-06 00:00:00.000000
"""

from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa


revision = "0002_cb202"
down_revision = "0001_cb207"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("category_name", sa.String(length=200), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("character_count", sa.BigInteger(), nullable=True),
        sa.Column("answer_source_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("reference_link_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("source_type IN ('FILE', 'WEB')", name="ck_data_sources_source_type"),
        sa.CheckConstraint("status IN ('PREPARING', 'TRAINING', 'AVAILABLE', 'ERROR')", name="ck_data_sources_status"),
        sa.CheckConstraint("priority IN ('HIGH', 'MEDIUM', 'LOW')", name="ck_data_sources_priority"),
    )
    for column in ("updated_at", "title", "format", "status", "source_type", "answer_source_enabled", "priority", "reference_link_visible"):
        op.create_index(f"ix_data_sources_{column}", "data_sources", [column])

    op.create_table(
        "data_source_files",
        sa.Column("data_source_id", sa.BigInteger(), sa.ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "data_source_websites",
        sa.Column("data_source_id", sa.BigInteger(), sa.ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "data_source_classification_values",
        sa.Column("data_source_id", sa.BigInteger(), sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("classification_type_id", sa.BigInteger(), sa.ForeignKey("classification_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("classification_value_id", sa.BigInteger(), sa.ForeignKey("classification_values.id", ondelete="RESTRICT"), nullable=False),
        sa.PrimaryKeyConstraint("data_source_id", "classification_type_id", name="pk_data_source_classification_values"),
    )
    op.create_index("ix_dscv_value_id", "data_source_classification_values", ["classification_value_id"])

    _insert_samples()


def _insert_samples() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    samples = [
        ("FILE", "［サンプル］2026年度奨学金募集要項", "pdf", "AVAILABLE", 128_000, 18_200, True, "HIGH", True, "sample_scholarship_2026.pdf", "application/pdf", None),
        ("FILE", "［サンプル］在学証明書申請案内", "docx", "AVAILABLE", 94_000, 9_800, True, "MEDIUM", True, "sample_enrollment.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None),
        ("FILE", "［サンプル］給付奨学金一覧", "xlsx", "TRAINING", 76_000, 7_200, True, "HIGH", False, "sample_grants.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None),
        ("FILE", "［サンプル］留学生向け支援制度", "pdf", "PREPARING", 203_000, None, True, "MEDIUM", True, "sample_international.pdf", "application/pdf", None),
        ("FILE", "［サンプル］奨学金FAQデータ", "txt", "AVAILABLE", 31_000, 12_500, False, "LOW", False, "sample_faq.txt", "text/plain", None),
        ("FILE", "［サンプル］学内貸与制度一覧", "csv", "AVAILABLE", 45_000, 6_400, True, "LOW", True, "sample_loans.csv", "text/csv", None),
        ("FILE", "［サンプル］申請時エラー確認用", "pdf", "ERROR", 52_000, None, False, "MEDIUM", True, "sample_error.pdf", "application/pdf", None),
        ("WEB", "［サンプル］大学奨学金案内サイト", "Web", "AVAILABLE", None, 24_000, True, "HIGH", True, None, None, "https://example.com/scholarships"),
        ("WEB", "［サンプル］日本学生支援機構案内", "Web", "AVAILABLE", None, 31_000, True, "HIGH", True, None, None, "https://example.com/jasso"),
        ("WEB", "［サンプル］入学予定者向け支援", "Web", "PREPARING", None, None, True, "MEDIUM", False, None, None, "https://example.com/new-students"),
        ("WEB", "［サンプル］Web学習中確認用", "Web", "TRAINING", None, 8_200, True, "LOW", True, None, None, "https://example.com/training"),
        ("WEB", "［サンプル］Web取得エラー確認用", "Web", "ERROR", None, None, False, "LOW", False, None, None, "https://example.com/error"),
    ]

    type_rows = connection.execute(sa.text("SELECT id, type_code FROM classification_types WHERE type_code IN ('TYPE_1','TYPE_2','TYPE_3')")).mappings().all()
    values_by_type: dict[int, list[int]] = {}
    for type_row in type_rows:
        values_by_type[type_row["id"]] = list(connection.execute(sa.text(
            "SELECT id FROM classification_values WHERE classification_type_id = :type_id ORDER BY display_order, id"
        ), {"type_id": type_row["id"]}).scalars())

    for index, sample in enumerate(samples):
        source_type, title, fmt, status, size_bytes, chars, answer, priority, reference, file_name, mime_type, url = sample
        existing_id = connection.execute(sa.text(
            "SELECT id FROM data_sources WHERE source_type = :source_type AND title = :title"
        ), {"source_type": source_type, "title": title}).scalar_one_or_none()
        if existing_id is not None:
            data_source_id = existing_id
        else:
            data_source_id = connection.execute(sa.text("""
                INSERT INTO data_sources
                  (source_type, title, format, status, category_name, size_bytes, character_count,
                   answer_source_enabled, priority, reference_link_visible, updated_at, version)
                VALUES
                  (:source_type, :title, :format, :status, NULL, :size_bytes, :character_count,
                   :answer, :priority, :reference, :updated_at, 1)
                RETURNING id
            """), {
                "source_type": source_type, "title": title, "format": fmt, "status": status,
                "size_bytes": size_bytes, "character_count": chars, "answer": answer,
                "priority": priority, "reference": reference,
                "updated_at": now - timedelta(hours=index * 3),
            }).scalar_one()

        if source_type == "FILE":
            connection.execute(sa.text("""
                INSERT INTO data_source_files (data_source_id, file_name, storage_key, mime_type)
                VALUES (:id, :file_name, NULL, :mime_type)
                ON CONFLICT (data_source_id) DO NOTHING
            """), {"id": data_source_id, "file_name": file_name, "mime_type": mime_type})
        else:
            connection.execute(sa.text("""
                INSERT INTO data_source_websites (data_source_id, url, last_fetched_at)
                VALUES (:id, :url, NULL)
                ON CONFLICT (data_source_id) DO NOTHING
            """), {"id": data_source_id, "url": url})

        for offset, type_row in enumerate(sorted(type_rows, key=lambda row: row["type_code"])):
            values = values_by_type.get(type_row["id"], [])
            if not values or (index + offset) % 4 == 3:
                continue
            value_id = values[(index + offset) % len(values)]
            connection.execute(sa.text("""
                INSERT INTO data_source_classification_values
                  (data_source_id, classification_type_id, classification_value_id)
                VALUES (:data_source_id, :type_id, :value_id)
                ON CONFLICT (data_source_id, classification_type_id) DO NOTHING
            """), {"data_source_id": data_source_id, "type_id": type_row["id"], "value_id": value_id})


def downgrade() -> None:
    op.drop_index("ix_dscv_value_id", table_name="data_source_classification_values")
    op.drop_table("data_source_classification_values")
    op.drop_table("data_source_websites")
    op.drop_table("data_source_files")
    for column in reversed(("updated_at", "title", "format", "status", "source_type", "answer_source_enabled", "priority", "reference_link_visible")):
        op.drop_index(f"ix_data_sources_{column}", table_name="data_sources")
    op.drop_table("data_sources")
