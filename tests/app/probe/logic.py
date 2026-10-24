import os
from decimal import Decimal
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from .models import Record

TEXT = "中文与 emoji 🧪 — apostrophe ' and slash \\"
PAYLOAD = {"name": "静态驱动", "items": [1, True, None, "🧪"]}
BINARY = b"\x00\x01\xffbinary\x00"

def create_record(token):
    return Record.objects.create(token=token, text=TEXT, amount=Decimal("12345.67"),
        payload=PAYLOAD, binary=BINARY, counter=0, created_at=timezone.now())

def check_record(record):
    assert record.text == TEXT
    assert record.amount == Decimal("12345.67")
    assert record.payload == PAYLOAD
    assert bytes(record.binary) == BINARY
    assert record.created_at.tzinfo is not None

def snapshot(record):
    check_record(record)
    with connection.cursor() as cursor:
        cursor.execute("SELECT CONNECTION_ID()")
        cid = cursor.fetchone()[0]
        cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        cipher = cursor.fetchone()[1]
    assert cipher, "Database connection must use TLS"
    return {"id": record.pk, "token": record.token, "counter": record.counter,
            "pid": os.getpid(), "connection_id": cid, "cipher": cipher}

def crud_cycle(token):
    with transaction.atomic():
        first = create_record(token)
        record = Record.objects.get(pk=first.pk)
        check_record(record)
        Record.objects.filter(pk=record.pk).update(counter=F("counter") + 1)
        record.refresh_from_db()
        assert record.counter == 1
        result = snapshot(record)
        record.delete()
        assert not Record.objects.filter(token=token).exists()
    return result
