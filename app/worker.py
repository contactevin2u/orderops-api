import threading, time
from .jobs import JobRunner

_job_runner = None

def start_worker():
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunner()
        thread = threading.Thread(target=_job_runner.run, daemon=True)
        thread.start()
