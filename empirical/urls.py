from django.urls import path

from . import views

app_name = 'empirical'

urlpatterns = [
    path('', views.run_algorithm, name="set_params"),
    path('export', views.handle_export_result, name="export"),
    path('threshold', views.calculate_threshold, name="threshold")
]