from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError


class PlayerProfile(models.Model):
    class Position(models.TextChoices):
        PG = "PG"
        SG = "SG"
        SF = "SF"
        PF = "PF"
        C = "C"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    position = models.CharField(max_length=2, choices=Position.choices)
    height_cm = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class Workout(models.Model):
    player = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name="workouts"
    )
    name = models.CharField(max_length=100)
    target_attempts = models.PositiveIntegerField(default=10)   # shots per session
    target_sessions = models.PositiveIntegerField(default=3)   # number of sessions
    goal_percentage = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.player})"

    @property
    def num_of_sessions(self):
        return self.sessions.count()

    @property
    def total_attempts(self):
        return self.target_attempts * self.num_of_sessions

    @property
    def total_makes(self):
        return self.sessions.aggregate(
            total=Sum("makes")
        )["total"] or 0

    @property
    def average_percentage(self):
        if self.total_attempts == 0:
            return 0
        return (self.total_makes / self.total_attempts) * 100

    @property
    def is_completed(self):
        return self.num_of_sessions >= self.target_sessions

    @property
    def is_successful(self):
        if not self.is_completed:
            return False
        return self.average_percentage >= self.goal_percentage


class WorkoutSession(models.Model):
    workout = models.ForeignKey(
        Workout,
        on_delete=models.CASCADE,
        related_name="sessions"
    )
    date = models.DateField()
    makes = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    @property
    def attempts(self):
        return self.workout.target_attempts

    @property
    def success_rate(self):
        if self.attempts == 0:
            return 0
        return (self.makes / self.attempts) * 100

    def clean(self):
        if self.makes > self.attempts:
            raise ValidationError("Makes cannot exceed attempts")

        if self.workout.is_completed:
            raise ValidationError("Workout is already completed")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workout.name} - {self.date}"
