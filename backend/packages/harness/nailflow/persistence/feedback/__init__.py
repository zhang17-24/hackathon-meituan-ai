"""Feedback persistence — ORM and SQL repository."""

from nailflow.persistence.feedback.model import FeedbackRow
from nailflow.persistence.feedback.sql import FeedbackRepository

__all__ = ["FeedbackRepository", "FeedbackRow"]
