from django.urls import path
from . import views

app_name = 'exports'

urlpatterns = [
    path('', views.clip_list_view, name='list'),
    path('<int:clip_id>/', views.clip_detail_view, name='detail'),
    path('<int:clip_id>/download/', views.clip_download_view, name='download'),
    path('<int:clip_id>/delete/', views.clip_delete_view, name='delete'),
]
