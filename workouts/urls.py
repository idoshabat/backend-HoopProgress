from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PlayerProfileViewSet, WorkoutViewSet, WorkoutSessionViewSet, LogoutView , LoginView , MeView ,  RegisterView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register("profiles", PlayerProfileViewSet, basename="profile")
router.register("workouts", WorkoutViewSet, basename="workout")
router.register("sessions", WorkoutSessionViewSet, basename="session")

urlpatterns = router.urls
urlpatterns += [
    path("token-auth/", obtain_auth_token),
    path("logout/", LogoutView.as_view(), name="logout"),  # no quotes
    path("login/", LoginView.as_view()),
    path("me/", MeView.as_view()),
    path("register/", RegisterView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),  # <-- refresh endpoint

]
