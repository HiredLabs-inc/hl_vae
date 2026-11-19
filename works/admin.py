from django.contrib import admin

from .models import Discipline, Institution, Publication, Subject, Topic, WorkType

admin.site.register(WorkType)
admin.site.register(Institution)
admin.site.register(Publication)
admin.site.register(Topic)
admin.site.register(Subject)
admin.site.register(Discipline)
