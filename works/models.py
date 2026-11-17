from django.db import models

class WorkType(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return f'{self.name} {self.id}'


class Institution(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return f'{self.name} {self.id}'


class Publication(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return f'{self.name} {self.id}'


class Topic(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return f'{self.name} {self.id}'


class Subject(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return f'{self.name} {self.id}'


class Discipline(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return f'{self.name} {self.id}'
