from django.contrib import admin

from .models import (
    Author,
    Discipline,
    Institution,
    Publication,
    Subject,
    Topic,
    Work,
    WorkType,
)

admin.site.register(WorkType)
admin.site.register(Institution)
admin.site.register(Publication)
admin.site.register(Topic)
admin.site.register(Subject)
admin.site.register(Discipline)
admin.site.register(Author)
admin.site.register(Work)
