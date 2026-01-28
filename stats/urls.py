from django.urls import path
from .views import StatsOverviewAPIView

urlpatterns = [
    path("overview/", StatsOverviewAPIView.as_view()),
]