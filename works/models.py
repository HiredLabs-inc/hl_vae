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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.id}"


class Discipline(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.id}"


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True)
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.discipline.name} , {self.subject.name} , #{self.id}"


class Author(models.Model):
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"


class Work(models.Model):
    title = models.CharField(max_length=200)
    link = models.URLField("", max_length=200, unique=True, blank=True, default="")
    file = models.FileField(
        (""), upload_to="uploads/", max_length=200, blank=True, default=""
    )
    published_date = models.DateField(null=True, blank=True)
    revised_date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True)
    institution = models.ForeignKey(
        Institution, on_delete=models.SET_NULL, null=True, blank=True
    )
    work_type = models.ForeignKey(WorkType, on_delete=models.SET_NULL, null=True)
    publication = models.ForeignKey(
        Publication, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"Title: {self.title}"
