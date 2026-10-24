"""Place this task in an existing Celery + Django application's tasks.py."""
from celery import shared_task
from django.db import connection


@shared_task
def mysql_server_version():
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        return cursor.fetchone()[0]
