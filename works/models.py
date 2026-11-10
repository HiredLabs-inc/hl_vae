from django.db import models


class Probe(models.Model):
    name = models.CharField(max_length=10)
