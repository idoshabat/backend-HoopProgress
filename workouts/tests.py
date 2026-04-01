from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PlayerProfile, Workout, WorkoutSession


User = get_user_model()


class WorkoutSessionByDateViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="player1",
            password="testpass123",
            role=User.Role.PLAYER,
        )
        self.player_profile = PlayerProfile.objects.create(
            user=self.user,
            position=PlayerProfile.Position.PG,
            height_cm=180,
            date_of_birth=date(2000, 1, 1),
        )
        self.workout = Workout.objects.create(
            player=self.player_profile,
            assigned_by=self.user,
            name="Form shooting",
            target_attempts=10,
            target_sessions=3,
            goal_percentage=70,
        )
        self.client.force_authenticate(user=self.user)

    def test_returns_only_sessions_for_requested_date(self):
        matching_session = WorkoutSession.objects.create(
            workout=self.workout,
            date=date(2026, 3, 31),
            makes=8,
        )
        WorkoutSession.objects.create(
            workout=self.workout,
            date=date(2026, 4, 1),
            makes=7,
        )

        response = self.client.get(
            reverse("session-by-date"),
            {"date": "2026-03-31"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], matching_session.id)

    def test_requires_valid_date_query_parameter(self):
        response = self.client.get(reverse("session-by-date"), {"date": "31-03-2026"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "date must be in YYYY-MM-DD format.")
