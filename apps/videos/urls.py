from django.urls import path
from . import views

app_name = 'videos'

urlpatterns = [
    path('', views.video_list_view, name='list'),
    path('upload/', views.upload_view, name='upload'),
    path('import-url/', views.import_url_view, name='import_url'),
    path('<int:video_id>/', views.video_detail_view, name='detail'),
    path('<int:video_id>/delete/', views.video_delete_view, name='delete'),
]
