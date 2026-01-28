from django.db.models import Sum, Count, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from collections import defaultdict
from datetime import datetime

from workouts.models import Workout, WorkoutSession


class StatsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get all workouts and sessions for the current user
        workouts = Workout.objects.filter(player__user=request.user)
        sessions = WorkoutSession.objects.filter(workout__in=workouts)

        # ---- COUNTS ----
        total_workouts = workouts.count()
        total_sessions = sessions.count()

        completed_workouts = workouts.annotate(
            session_count=Count("sessions")
        ).filter(session_count__gte=F("target_sessions")).count()

        in_progress_workouts = total_workouts - completed_workouts

        # ---- MAKES ----
        total_makes = sum((s.makes or 0) for s in sessions)

        # ---- ATTEMPTS (derived safely) ----
        total_attempts = sum(
            (w.target_attempts or 0) * w.sessions.count()
            for w in workouts
        )

        overall_success_rate = (
            (total_makes / total_attempts) * 100
            if total_attempts > 0 else 0
        )

        # ---- BEST WORKOUT ----
        best_workout_rate = max(
            (w.average_percentage or 0 for w in workouts),
            default=0
        )

        # ---- PROGRESS OVER TIME ----
        progress_dict = defaultdict(lambda: {"total_makes": 0, "session_count": 0})

        for s in sessions:
            if s.date is None or s.workout.target_attempts is None:
                continue
            day = s.date.date() if hasattr(s.date, "date") else s.date
            progress_dict[day]["total_makes"] += s.makes or 0
            progress_dict[day]["session_count"] += 1
            progress_dict[day]["target_attempts"] = s.workout.target_attempts or 0

        progress_over_time = []
        for day in sorted(progress_dict.keys()):
            data = progress_dict[day]
            attempts = data["target_attempts"] * data["session_count"]
            rate = (data["total_makes"] / attempts) * 100 if attempts > 0 else 0
            progress_over_time.append({
                "date": day,
                "avg_success_rate": round(rate, 2)
            })

        return Response({
            "total_workouts": total_workouts,
            "completed_workouts": completed_workouts,
            "in_progress_workouts": in_progress_workouts,
            "total_sessions": total_sessions,
            "total_attempts": total_attempts,
            "total_makes": total_makes,
            "overall_success_rate": round(overall_success_rate, 2),
            "best_workout_success_rate": round(best_workout_rate, 2),
            "progress_over_time": progress_over_time,
        })
