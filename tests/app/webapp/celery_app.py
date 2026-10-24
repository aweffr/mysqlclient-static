import os
import sys

if sys.platform == "darwin":
    import billiard

    # This test exercises a prefork pool; macOS otherwise selects spawn.
    billiard.set_start_method("fork", force=True)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
from celery import Celery
app = Celery("mysqlclient-static-e2e", broker=os.environ["CELERY_URL"], backend=os.environ["CELERY_URL"],
             include=["probe.tasks"])
app.conf.update(task_always_eager=False, task_serializer="json", result_serializer="json",
                accept_content=["json"], worker_prefetch_multiplier=1,
                task_default_queue=os.environ["CELERY_QUEUE"], result_expires=300,
                broker_connection_retry_on_startup=True)
