# dashboard_app/urls.py
from django.urls import path
from . import views

app_name = 'dashboard_app'

urlpatterns = [
    path('', views.upload_csv, name='upload_csv'),  # raíz -> upload
    path('preview/<int:pk>/', views.preview_dataset, name='preview_dataset'),
    path('delete/<int:pk>/', views.delete_dataset, name='delete_dataset'),
]
