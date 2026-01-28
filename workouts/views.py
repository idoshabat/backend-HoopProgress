from rest_framework import viewsets, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, F, BooleanField, ExpressionWrapper, Q

from .models import Workout, WorkoutSession, PlayerProfile
from .serializers import (
    PlayerProfileSerializer,
    WorkoutSerializer,
    WorkoutSessionSerializer,
    RegisterSerializer,
)


class PlayerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PlayerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PlayerProfile.objects.filter(user=self.request.user)


class WorkoutViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            Workout.objects
            .filter(player__user=self.request.user)
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

    def perform_create(self, serializer):
        player = get_object_or_404(PlayerProfile, user=self.request.user)
        serializer.save(player=player)


class WorkoutSessionViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WorkoutSession.objects.filter(
            workout__player__user=self.request.user
        )

    def perform_create(self, serializer):
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


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )

        if not user:
            return Response({"detail": "Invalid credentials"}, status=400)

        refresh = RefreshToken.for_user(user)

        response = Response({
            "access": str(refresh.access_token),
        })

        response.set_cookie(
            key="refresh",
            value=str(refresh),
            httponly=True,
            secure=False,
            samesite="Lax",
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
        return Response({
            "id": request.user.id,
            "username": request.user.username,
        })
