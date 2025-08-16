import uuid, time
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Job

class JobRunner:
    def __init__(self):
        self.session_factory = SessionLocal

    def run(self):
        while True:
            time.sleep(1)
            try:
                with self.session_factory.begin() as db:
                    job = db.query(Job).filter(Job.status == "PENDING").first()
                    if job:
                        job.status = "DONE"
                        job.result_url = job.result_url or ""
            except Exception:
                continue

def create_job(db: Session, kind: str, result_url: str = "") -> Job:
    job = Job(job_id=str(uuid.uuid4()), kind=kind, status="PENDING", result_url=result_url)
    db.add(job)
    db.flush()
    return job
