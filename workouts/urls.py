from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ConnectionRequestListView, FindPlayerByUsernameView, AddPlayerToCoachView,AddCoachToPlayerView, RemoveCoachFromPlayerView,FindCoachByUsernameView, PlayerProfileViewSet,CoachProfileViewSet, RemovePlayerFromCoachView, RespondConnectionRequestView, WorkoutViewSet, WorkoutSessionViewSet, LogoutView , LoginView , MobileLoginView, CookieTokenRefreshView, MobileTokenRefreshView, MeView ,  RegisterView, MobileRegisterView, WorkoutTemplateViewSet, NotificationViewSet, RegisterDevicePushTokenView, DeactivateDevicePushTokenView
from rest_framework.authtoken.views import obtain_auth_token

router = DefaultRouter()
router.register("players-profiles", PlayerProfileViewSet, basename="profile")
router.register("coaches-profiles", CoachProfileViewSet, basename="coach-profile")
router.register("workouts", WorkoutViewSet, basename="workout")
router.register("sessions", WorkoutSessionViewSet, basename="session")
router.register("workout-templates", WorkoutTemplateViewSet, basename="workout-template")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = router.urls
urlpatterns += [
    path("token-auth/", obtain_auth_token),
    path("logout/", LogoutView.as_view(), name="logout"),  # no quotes
    path("login/", LoginView.as_view()),
    path("login/mobile/", MobileLoginView.as_view()),
    path("me/", MeView.as_view()),
    path("register/", RegisterView.as_view()),
    path("register/mobile/", MobileRegisterView.as_view()),
    path("token/refresh/", CookieTokenRefreshView.as_view()),
    path("token/refresh/mobile/", MobileTokenRefreshView.as_view()),
    path("push-tokens/register/", RegisterDevicePushTokenView.as_view()),
    path("push-tokens/deactivate/", DeactivateDevicePushTokenView.as_view()),
    path("add-coach-to-player/", AddCoachToPlayerView.as_view(), name="add-coach-to-player"),
    path("add-player-to-coach/", AddPlayerToCoachView.as_view(), name="add-player-to-coach"),
    path("connection-requests/", ConnectionRequestListView.as_view(), name="connection-request-list"),
    path("connection-requests/<int:request_id>/respond/", RespondConnectionRequestView.as_view(), name="respond-connection-request"),
    path("find-player/", FindPlayerByUsernameView.as_view(), name="find-player"),
    path("find-coach/", FindCoachByUsernameView.as_view(), name="find-coach"),
    path("remove-coach-from-player/", RemoveCoachFromPlayerView.as_view(), name="remove-coach-from-player"),
    path("remove-player-from-coach/", RemovePlayerFromCoachView.as_view(), name="remove-player-from-coach"),
]
