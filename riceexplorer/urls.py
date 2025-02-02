"""riceexplorer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
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
from django.urls import path, include, re_path

from .views import get_task_with_id, home, get_tasks, handle_download_file

urlpatterns = [
    path('', home, name="home"),
    path('admin/', admin.site.urls, name="admin"),
    path('phenology/', include('phenology.urls')),
    path('empirical/', include('empirical.urls')),
    path('classification/', include('classification.urls')),
    path('myapp/', include('myapp.urls')),
    
    path("tasks/<str:id>", get_task_with_id),
    path("tasks/", get_tasks),
    
    path("download/<str:id>", handle_download_file),

    re_path(r"^$", home),
    re_path(r"^(?:.*)/?$", home),
    # path('api-auth/', include('rest_framework.urls')),
]
