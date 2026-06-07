"""ORM model registration entry point.

Importing this module ensures all ORM models are registered with
``Base.metadata`` so Alembic autogenerate detects every table.

The actual ORM classes have moved to entity-specific subpackages:
- ``nailflow.persistence.thread_meta``
- ``nailflow.persistence.run``
- ``nailflow.persistence.feedback``
- ``nailflow.persistence.user``

``RunEventRow`` remains in ``nailflow.persistence.models.run_event`` because
its storage implementation lives in ``nailflow.runtime.events.store.db`` and
there is no matching entity directory.
"""

from nailflow.persistence.feedback.model import FeedbackRow
from nailflow.persistence.models.run_event import RunEventRow
from nailflow.persistence.run.model import RunRow
from nailflow.persistence.thread_meta.model import ThreadMetaRow
from nailflow.persistence.user.model import UserRow

__all__ = ["FeedbackRow", "RunEventRow", "RunRow", "ThreadMetaRow", "UserRow"]
