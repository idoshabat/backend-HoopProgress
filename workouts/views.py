from rest_framework import viewsets, serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, F, BooleanField, ExpressionWrapper, Q
from rest_framework.decorators import action
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date
from .models import ConnectionRequest, User


from .models import Workout, WorkoutSession, PlayerProfile, CoachProfile
from .serializers import (
    ConnectionRequestSerializer,
    PlayerProfileSerializer,
    CoachProfileSerializer,
    WorkoutSerializer,
    WorkoutSessionSerializer,
    RegisterSerializer,
)


class PlayerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PlayerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PlayerProfile.objects.select_related("user").prefetch_related("coaches")
        if self.action == "retrieve":
            return queryset
        if self.action in {"list", "update", "partial_update", "destroy"}:
            return queryset.filter(user=self.request.user)
        return queryset.filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        profile = PlayerProfile.objects.get(user=request.user)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
class CoachProfileViewSet(viewsets.ModelViewSet):
    serializer_class = CoachProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CoachProfile.objects.select_related("user").prefetch_related("players__user")
        if self.action == "retrieve":
            return queryset
        if self.action in {"list", "update", "partial_update", "destroy"}:
            return queryset.filter(user=self.request.user)
        return queryset.filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        profile = CoachProfile.objects.get(user=request.user)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

class WorkoutViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSerializer
    permission_classes = [IsAuthenticated]

    def _visible_workouts(self):
        if self.request.user.role == User.Role.COACH:
            return Workout.objects.filter(player__coaches__user=self.request.user).distinct()
        return Workout.objects.filter(player__user=self.request.user)

    def _annotated_workouts(self, queryset):
        qs = (
            queryset
            .annotate(
                num_of_sessions_db=Count("sessions"),
                is_completed_db=ExpressionWrapper(
                    Q(num_of_sessions_db__gte=F("target_sessions")),
                    output_field=BooleanField()
                )
            )
        )

        status = self.request.query_params.get("status")

        if status == "completed":
            qs = qs.filter(is_completed_db=True)
        elif status == "in_progress":
            qs = qs.filter(is_completed_db=False)

        return qs

    def get_queryset(self):
        return self._annotated_workouts(self._visible_workouts())

    def perform_create(self, serializer):
        if self.request.user.role == User.Role.COACH:
            coach_profile = get_object_or_404(CoachProfile, user=self.request.user)
            player = serializer.validated_data.get("player")

            if player is None:
                raise serializers.ValidationError({"player": "This field is required."})

            if not coach_profile.players.filter(pk=player.pk).exists():
                raise serializers.ValidationError(
                    {"player": "You can only assign workouts to your own players."}
                )
        else:
            player = get_object_or_404(PlayerProfile, user=self.request.user)

        serializer.save(player=player, assigned_by=self.request.user)
        
    def update(self, request, *args, **kwargs):
        workout = self.get_object()

        if workout.sessions.count() >= workout.target_sessions:
            return Response(
                {"detail": "Completed workouts cannot be edited."},
                status=403
            )

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        workout = self.get_object()
        workout.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

    @action(detail=False, methods=["get"], url_path="assigned-by-me")
    def assigned_by_me(self, request):
        workouts = self.get_queryset().filter(assigned_by=request.user)
        serializer = self.get_serializer(workouts, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"assigned-by-me/player/(?P<player_id>[^/.]+)",
    )
    def assigned_by_me_for_player(self, request, player_id=None):
        if request.user.role != User.Role.COACH:
            return Response(
                {"detail": "Only coaches can view workouts they assigned to a specific player."},
                status=status.HTTP_403_FORBIDDEN,
            )

        coach_profile = get_object_or_404(CoachProfile, user=request.user)
        player = get_object_or_404(PlayerProfile, id=player_id)

        if not coach_profile.players.filter(id=player.id).exists():
            return Response(
                {"detail": "You can only view workouts for your own players."},
                status=status.HTTP_403_FORBIDDEN,
            )

        workouts = self.get_queryset().filter(
            assigned_by=request.user,
            player=player,
        )
        serializer = self.get_serializer(workouts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="assigned-by-my-coaches")
    def assigned_by_my_coaches(self, request):
        if request.user.role != User.Role.PLAYER:
            return Response(
                {"detail": "Only players can view workouts assigned by their coaches."},
                status=status.HTTP_403_FORBIDDEN,
            )

        player = get_object_or_404(PlayerProfile, user=request.user)
        workouts = self.get_queryset().filter(
            assigned_by__coachprofile__players=player
        ).exclude(
            assigned_by=request.user
        ).distinct()
        serializer = self.get_serializer(workouts, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"assigned-by-my-coaches/(?P<coach_id>[^/.]+)",
    )
    def assigned_by_specific_coach(self, request, coach_id=None):
        if request.user.role != User.Role.PLAYER:
            return Response(
                {"detail": "Only players can view workouts assigned by a specific coach."},
                status=status.HTTP_403_FORBIDDEN,
            )

        player = get_object_or_404(PlayerProfile, user=request.user)
        coach = get_object_or_404(CoachProfile, id=coach_id)

        if not player.coaches.filter(id=coach.id).exists():
            return Response(
                {"detail": "You can only view workouts assigned by your own coaches."},
                status=status.HTTP_403_FORBIDDEN,
            )

        workouts = self.get_queryset().filter(
            assigned_by=coach.user,
            player=player,
        )
        serializer = self.get_serializer(workouts, many=True)
        return Response(serializer.data)



class WorkoutSessionViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WorkoutSession.objects.select_related("workout").filter(
            workout__player__user=self.request.user
        )

    def _get_requested_date(self, request):
        date_value = request.query_params.get("date", "").strip()

        if not date_value:
            return None, Response(
                {"detail": "date query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parsed_date = parse_date(date_value)
        if parsed_date is None:
            return None, Response(
                {"detail": "date must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return parsed_date, None

    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        parsed_date, error_response = self._get_requested_date(request)
        if error_response is not None:
            return error_response

        sessions = self.get_queryset().filter(date=parsed_date)
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="my-players/by-date")
    def my_players_by_date(self, request):
        if request.user.role != User.Role.COACH:
            return Response(
                {"detail": "Only coaches can view sessions for their players."},
                status=status.HTTP_403_FORBIDDEN,
            )

        parsed_date, error_response = self._get_requested_date(request)
        if error_response is not None:
            return error_response

        sessions = WorkoutSession.objects.select_related(
            "workout",
            "workout__player",
            "workout__player__user",
        ).filter(
            workout__player__coaches__user=request.user,
            date=parsed_date,
        ).distinct()
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.PLAYER:
            raise serializers.ValidationError(
                "Only players can create workout sessions."
            )
            
        workout = get_object_or_404(
            Workout,
            id=self.request.data.get("workout"),
            player__user=self.request.user
        )

        if workout.is_completed:
            raise serializers.ValidationError(
                "Workout is already completed"
            )

        serializer.save(workout=workout)
        
    # def perform_update(self, serializer):
    #     session = self.get_object()
    #     workout = session.workout
        
                
    #     return super().perform_update(serializer)
        
    def destroy(self, request, *args, **kwargs):
        session = self.get_object()
        workout = session.workout

        if workout.sessions.count() >= workout.target_sessions:
            return Response(
                {"detail": "Cannot delete session from a completed workout."},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        # Authenticate the user
        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )

        if not user:
            return Response({"detail": "Invalid credentials"}, status=400)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Determine cookie settings based on environment
        if settings.DEBUG:
            cookie_secure = False  # HTTP on local
            cookie_samesite = "Lax"
        else:
            cookie_secure = True   # HTTPS in production
            cookie_samesite = "None"

        response = Response({
            "access": access_token,
        })

        # Set refresh cookie
        response.set_cookie(
            key="refresh",
            value=str(refresh),
            httponly=True,
            secure=cookie_secure,
            samesite=cookie_samesite,
            path="/",  # important: available to all routes
        )

        return response

class LogoutView(APIView):
    def post(self, request):
        response = Response({"detail": "Logged out"})
        response.delete_cookie("refresh")
        return response


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        response = Response({
            "access": str(refresh.access_token),
            "role": user.role,
            "username": user.username,
        })

        response.set_cookie(
            key="refresh",
            value=str(refresh),
            httponly=True,
            secure=False,
            samesite="Lax",
        )

        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "id": request.user.id,
            "username": request.user.username,
            "role": request.user.role,
        }
        if request.user.role == User.Role.PLAYER:
            profile = PlayerProfile.objects.get(user=request.user)
            data["position"] = profile.position
            data["height_cm"] = profile.height_cm
            data["date_of_birth"] = profile.date_of_birth
            data["coaches"] = CoachProfileSerializer(profile.coaches.all(), many=True).data
        elif request.user.role == User.Role.COACH:
            profile = CoachProfile.objects.get(user=request.user)
            data["date_of_birth"] = profile.date_of_birth
            data["players"] = PlayerProfileSerializer(profile.players.all(), many=True).data
        return Response(data)


def create_connection_request(sender, receiver):
    connection_request = ConnectionRequest(sender=sender, receiver=receiver)
    connection_request.save()
    return connection_request


class AddPlayerToCoachView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != User.Role.COACH:
            return Response(
                {"detail": "Only coaches can send player connection requests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        coach_profile = get_object_or_404(CoachProfile, user=request.user)
        player_id = request.data.get("player_id")
        player_profile = get_object_or_404(PlayerProfile, id=player_id)
        if player_profile in coach_profile.players.all():
            return Response({"detail": "Player is already connected to this coach."}, status=400)

        try:
            connection_request = create_connection_request(
                sender=request.user,
                receiver=player_profile.user,
            )
        except ValidationError as exc:
            detail = exc.messages[0] if exc.messages else "Could not create connection request."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ConnectionRequestSerializer(connection_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class AddCoachToPlayerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != User.Role.PLAYER:
            return Response(
                {"detail": "Only players can send coach connection requests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        player_profile = get_object_or_404(PlayerProfile, user=request.user)
        coach_id = request.data.get("coach_id")
        coach_profile = get_object_or_404(CoachProfile, id=coach_id)
        if coach_profile in player_profile.coaches.all():
            return Response({"detail": "Coach is already connected to this player."}, status=400)

        try:
            connection_request = create_connection_request(
                sender=request.user,
                receiver=coach_profile.user,
            )
        except ValidationError as exc:
            detail = exc.messages[0] if exc.messages else "Could not create connection request."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ConnectionRequestSerializer(connection_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConnectionRequestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request_type = request.query_params.get("type", "incoming").strip().lower()
        request_status = request.query_params.get("status", ConnectionRequest.Status.PENDING).strip().upper()

        if request_type == "outgoing":
            queryset = ConnectionRequest.objects.filter(sender=request.user)
        else:
            queryset = ConnectionRequest.objects.filter(receiver=request.user)

        if request_status:
            queryset = queryset.filter(status=request_status)

        serializer = ConnectionRequestSerializer(queryset, many=True)
        return Response(serializer.data)


class RespondConnectionRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        connection_request = get_object_or_404(
            ConnectionRequest,
            id=request_id,
            receiver=request.user,
        )

        if connection_request.status != ConnectionRequest.Status.PENDING:
            return Response(
                {"detail": "This request has already been handled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action_name = request.data.get("action", "").strip().lower()
        if action_name not in {"accept", "reject"}:
            return Response(
                {"detail": "action must be either 'accept' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action_name == "accept":
            if connection_request.sender.role == User.Role.COACH:
                coach_profile = get_object_or_404(CoachProfile, user=connection_request.sender)
                player_profile = get_object_or_404(PlayerProfile, user=connection_request.receiver)
            else:
                coach_profile = get_object_or_404(CoachProfile, user=connection_request.receiver)
                player_profile = get_object_or_404(PlayerProfile, user=connection_request.sender)

            coach_profile.players.add(player_profile)
            connection_request.status = ConnectionRequest.Status.ACCEPTED
        else:
            connection_request.status = ConnectionRequest.Status.REJECTED

        connection_request.save()
        serializer = ConnectionRequestSerializer(connection_request)
        return Response(serializer.data)

class FindPlayerByUsernameView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.COACH:
            return Response(
                {"detail": "Only coaches can search for players."},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = request.query_params.get("username", "").strip()
        if not username:
            return Response(
                {"detail": "username query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        players = PlayerProfile.objects.filter(
            user__username__icontains=username
        ).select_related("user")

        serializer = PlayerProfileSerializer(players, many=True)
        return Response(serializer.data)


class FindCoachByUsernameView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.PLAYER:
            return Response(
                {"detail": "Only players can search for coaches."},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = request.query_params.get("username", "").strip()
        if not username:
            return Response(
                {"detail": "username query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coaches = CoachProfile.objects.filter(
            user__username__icontains=username
        ).select_related("user")

        serializer = CoachProfileSerializer(coaches, many=True)
        return Response(serializer.data)

class RemovePlayerFromCoachView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        coach_profile = get_object_or_404(CoachProfile, user=request.user)
        player_id = request.data.get("player_id")
        player_profile = get_object_or_404(PlayerProfile, id=player_id)
        if player_profile not in coach_profile.players.all():
            return Response({"detail": "Player is not assigned to this coach."}, status=400)
        coach_profile.players.remove(player_profile)
        return Response({"detail": f"Player {player_profile.user.username} removed from coach {coach_profile.user.username}"})

class RemoveCoachFromPlayerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        player_profile = get_object_or_404(PlayerProfile, user=request.user)
        coach_id = request.data.get("coach_id")
        coach_profile = get_object_or_404(CoachProfile, id=coach_id)
        if coach_profile not in player_profile.coaches.all():
            return Response({"detail": "Coach is not assigned to this player."}, status=400)
        player_profile.coaches.remove(coach_profile)
        return Response({"detail": f"Coach {coach_profile.user.username} removed from player {player_profile.user.username}"})
