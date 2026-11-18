from django.db import models


class WorkType(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.id}"


class Institution(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.id}"


class Publication(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.id}"


class Subject(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return f"{self.name} {self.id}"


class Discipline(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return f"{self.name} {self.id}"


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True)
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.discipline.name} , {self.subject.name} , #{self.id}"
