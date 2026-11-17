from django.contrib import admin
from .models import WorkType
from .models import Institution
from .models import Publication
from .models import Topic
from .models import Subject
from .models import Discipline


admin.site.register(WorkType)
admin.site.register(Institution)
admin.site.register(Publication)
admin.site.register(Topic)
admin.site.register(Subject)
admin.site.register(Discipline)
