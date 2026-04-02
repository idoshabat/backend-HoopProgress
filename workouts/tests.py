from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CoachProfile, PlayerProfile, Workout, WorkoutSession


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


class CoachWorkoutSessionByDateViewTests(APITestCase):
    def setUp(self):
        self.coach_user = User.objects.create_user(
            username="coach1",
            password="testpass123",
            role=User.Role.COACH,
        )
        self.coach_profile = CoachProfile.objects.create(
            user=self.coach_user,
            date_of_birth=date(1985, 1, 1),
        )

        self.player_user = User.objects.create_user(
            username="player1",
            password="testpass123",
            role=User.Role.PLAYER,
        )
        self.player_profile = PlayerProfile.objects.create(
            user=self.player_user,
            position=PlayerProfile.Position.PG,
            height_cm=180,
            date_of_birth=date(2000, 1, 1),
        )
        self.coach_profile.players.add(self.player_profile)

        self.other_player_user = User.objects.create_user(
            username="player2",
            password="testpass123",
            role=User.Role.PLAYER,
        )
        self.other_player_profile = PlayerProfile.objects.create(
            user=self.other_player_user,
            position=PlayerProfile.Position.SG,
            height_cm=182,
            date_of_birth=date(2001, 2, 2),
        )

        self.workout = Workout.objects.create(
            player=self.player_profile,
            assigned_by=self.coach_user,
            name="Form shooting",
            target_attempts=10,
            target_sessions=3,
            goal_percentage=70,
        )
        self.other_workout = Workout.objects.create(
            player=self.other_player_profile,
            assigned_by=self.other_player_user,
            name="Off-dribble shooting",
            target_attempts=10,
            target_sessions=3,
            goal_percentage=65,
        )

    def test_coach_gets_only_sessions_of_their_players_for_requested_date(self):
        matching_session = WorkoutSession.objects.create(
            workout=self.workout,
            date=date(2026, 4, 2),
            makes=8,
        )
        WorkoutSession.objects.create(
            workout=self.workout,
            date=date(2026, 4, 1),
            makes=7,
        )
        WorkoutSession.objects.create(
            workout=self.other_workout,
            date=date(2026, 4, 2),
            makes=9,
        )

        self.client.force_authenticate(user=self.coach_user)
        response = self.client.get(
            reverse("session-my-players-by-date"),
            {"date": "2026-04-02"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], matching_session.id)

    def test_non_coach_cannot_use_my_players_by_date_view(self):
        self.client.force_authenticate(user=self.player_user)

        response = self.client.get(
            reverse("session-my-players-by-date"),
            {"date": "2026-04-02"},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data["detail"],
            "Only coaches can view sessions for their players.",
        )
