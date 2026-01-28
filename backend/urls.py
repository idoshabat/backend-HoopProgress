from django.urls import path, include
from django.contrib import admin


urlpatterns = [
    path("api/", include("workouts.urls")),
    path("admin/", admin.site.urls),
    path("api/stats/", include("stats.urls")),

]
