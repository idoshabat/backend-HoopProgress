from django.db.models import Count , F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from collections import defaultdict

from workouts.models import Workout, WorkoutSession


class StatsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workouts = Workout.objects.filter(player__user=request.user)
        sessions = WorkoutSession.objects.filter(workout__in=workouts)

        # ---- COUNTS ----
        total_workouts = workouts.count()
        total_sessions = sessions.count()

        completed_workouts_qs = workouts.filter(
            sessions__isnull=False
        ).annotate(
            session_count=Count("sessions")
        ).filter(session_count__gte=F("target_sessions")).distinct()

        completed_workouts = completed_workouts_qs.count()
        in_progress_workouts = total_workouts - completed_workouts

        # ---- SUCCESS / FAILURE ----
        successful_workouts = sum(1 for w in completed_workouts_qs if w.is_successful)
        failed_workouts = completed_workouts - successful_workouts

        completed_success_rate = (
            (successful_workouts / completed_workouts) * 100
            if completed_workouts > 0 else 0
        )

        # ---- MAKES / ATTEMPTS ----
        total_makes = sum((s.makes or 0) for s in sessions)
        total_attempts = sum(
            (w.target_attempts or 0) * w.sessions.count()
            for w in workouts
        )

        overall_success_rate = (
            (total_makes / total_attempts) * 100
            if total_attempts > 0 else 0
        )

        # ---- BEST WORKOUT ----
        best_workout = max(
            workouts,
            key=lambda w: w.average_percentage or 0,
            default=None
        )

        best_workout_name = best_workout.name if best_workout else None
        best_workout_rate = best_workout.average_percentage if best_workout else 0

        # ---- PROGRESS OVER TIME ----
        progress = defaultdict(lambda: {"makes": 0, "sessions": 0, "attempts": 0})

        for s in sessions:
            day = s.date
            progress[day]["makes"] += s.makes or 0
            progress[day]["sessions"] += 1
            progress[day]["attempts"] += s.workout.target_attempts or 0

        progress_over_time = []
        for day in sorted(progress.keys()):
            data = progress[day]
            attempts = data["attempts"]
            rate = (data["makes"] / attempts) * 100 if attempts > 0 else 0
            progress_over_time.append({
                "date": day,
                "avg_success_rate": round(rate, 2)
            })
        
        

        return Response({
            "total_workouts": total_workouts,
            "completed_workouts": completed_workouts,
            "in_progress_workouts": in_progress_workouts,
            "successful_workouts": successful_workouts,
            "failed_workouts": failed_workouts,
            "completed_success_rate": round(completed_success_rate, 2),
            "total_sessions": total_sessions,
            "overall_success_rate": round(overall_success_rate, 2),
            "best_workout_name": best_workout_name,
            "best_workout_success_rate": round(best_workout_rate, 2),
            "progress_over_time": progress_over_time,
        })
