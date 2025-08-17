import hashlib
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models import Message

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def get_message_by_sha(db, sha: str):
    return db.execute(select(Message).where(Message.sha256 == sha)).scalar_one_or_none()

def upsert_message(db, sha: str, text: str, parsed_dict):
    """
    Insert a Message if not exists; if exists, return it.
    If existing has parsed_json NULL and parsed_dict provided, backfill it.
    """
    stmt = (
        insert(Message)
        .values(sha256=sha, text=text, parsed_json=parsed_dict)
        .on_conflict_do_nothing(index_elements=[Message.sha256])
        .returning(Message.id)
    )
    new_id = db.execute(stmt).scalar_one_or_none()
    if new_id is not None:
        db.commit()
        return db.get(Message, new_id)

    # Already exists -> fetch and maybe backfill parsed_json/text
    msg = get_message_by_sha(db, sha)
    if msg is not None and msg.parsed_json is None and parsed_dict is not None:
        msg.parsed_json = parsed_dict
        if not msg.text:
            msg.text = text
        db.commit()
        db.refresh(msg)
    return msg