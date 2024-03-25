from django.urls import path
from .views import crop_data

urlpatterns = [
    path('crop_data/', crop_data, name='crop_data'),
]
    