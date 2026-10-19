"""Row locking shared by version, project, and task mutations."""
from sqlalchemy import update
from sqlalchemy.orm import Session


def lock_record(db: Session, model, record_id: str):
    """Serialize a write before reading its invariants on PostgreSQL and SQLite.

    SQLite ignores SELECT FOR UPDATE. An explicit no-op update obtains its write
    reservation before counting versions or assigning task codes. The surrounding
    endpoint retains the transaction through all dependent writes.
    """
    if db.get_bind().dialect.name == "sqlite":
        values = {"id": model.id}
        if hasattr(model, "updated_at"):
            values["updated_at"] = model.updated_at
        db.execute(update(model).where(model.id == record_id).values(**values))
    return db.query(model).filter(model.id == record_id).populate_existing().with_for_update().first()
