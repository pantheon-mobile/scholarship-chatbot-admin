"""Import every ORM model so SQLAlchemy can resolve string relationships."""

from app.models.analytics import AccessLog, AnalyticsVisitor, ChatFeedback, ChatInteraction, ChatSession
from app.models.auth import AdminOperationLog, AuthSession, CpfUsedJti
from app.models.category import Category
from app.models.classification import ClassificationType, ClassificationValue
from app.models.data_source import (
    DataSource,
    DataSourceClassificationValue,
    DataSourceFile,
    DataSourceWebsite,
    IngestionJob,
)
from app.models.faq import Faq, FaqClassificationAssignment, FaqSimilarQuestion
from app.models.faq_classification import FaqClassificationType, FaqClassificationValue

__all__ = [
    "AccessLog",
    "AdminOperationLog",
    "AnalyticsVisitor",
    "AuthSession",
    "Category",
    "ChatFeedback",
    "ChatInteraction",
    "ChatSession",
    "ClassificationType",
    "ClassificationValue",
    "CpfUsedJti",
    "DataSource",
    "DataSourceClassificationValue",
    "DataSourceFile",
    "DataSourceWebsite",
    "Faq",
    "FaqClassificationAssignment",
    "FaqClassificationType",
    "FaqClassificationValue",
    "FaqSimilarQuestion",
    "IngestionJob",
]
