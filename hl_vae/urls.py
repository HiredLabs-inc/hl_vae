"""
URL configuration for hl_vae project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from works import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home_view, name="index"),
    path("about/", views.about_view, name="about"),
    path("works/", views.works_view, name="works"),
    path("submit_a_work/", views.submit_a_work_view, name="submit_a_work"),
    path("reviewer/", views.reviewer_view, name="reviewer"),
] + static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)