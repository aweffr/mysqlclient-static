from django.db import models

class Record(models.Model):
    token = models.CharField(max_length=64, unique=True)
    text = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payload = models.JSONField()
    binary = models.BinaryField()
    counter = models.IntegerField(default=0)
    created_at = models.DateTimeField()
