from django.urls import path
from . import views

app_name = 'processing'

urlpatterns = [
    path('create/<int:video_id>/', views.create_job_view, name='create_job'),
    path('jobs/<int:job_id>/', views.job_detail_view, name='job_detail'),
    path('jobs/<int:job_id>/status/', views.job_status_api, name='job_status_api'),
    path('jobs/<int:job_id>/cancel/', views.cancel_job_view, name='cancel_job'),
    path('jobs/<int:job_id>/retry/', views.retry_job_view, name='retry_job'),
]
