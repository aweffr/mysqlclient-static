from celery import shared_task
from .logic import crud_cycle

@shared_task
def database_cycle(token):
    return crud_cycle(token)
