from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    class Role(models.TextChoices):
        PLAYER = "PLAYER"
        COACH = "COACH"

    role = models.CharField(max_length=10, choices=Role.choices)


class PlayerProfile(models.Model):
    class Position(models.TextChoices):
        PG = "PG"
        SG = "SG"
        SF = "SF"
        PF = "PF"
        C = "C"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    position = models.CharField(max_length=2, choices=Position.choices)
    height_cm = models.PositiveIntegerField(default=180)
    date_of_birth = models.DateField(default="2000-01-01")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username
    
class CoachProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    players = models.ManyToManyField(PlayerProfile, related_name="coaches", blank=True)


    def __str__(self):
        return self.user.username


class ConnectionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        ACCEPTED = "ACCEPTED"
        REJECTED = "REJECTED"
        CANCELED = "CANCELED"

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_connection_requests",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_connection_requests",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "receiver"],
                condition=Q(status="PENDING"),
                name="unique_pending_connection_request",
            ),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"

    def clean(self):
        super().clean()

        if self.sender_id == self.receiver_id:
            raise ValidationError("You cannot send a connection request to yourself.")

        if self.sender.role == self.receiver.role:
            raise ValidationError("Connection requests must be between a player and a coach.")

        if self.status != self.Status.PENDING:
            return

        sender_is_connected = CoachProfile.objects.filter(
            user=self.sender,
            players__user=self.receiver,
        ).exists()
        receiver_is_connected = CoachProfile.objects.filter(
            user=self.receiver,
            players__user=self.sender,
        ).exists()

        if sender_is_connected or receiver_is_connected:
            raise ValidationError("These users are already connected.")

        opposite_pending_exists = ConnectionRequest.objects.filter(
            sender=self.receiver,
            receiver=self.sender,
            status=self.Status.PENDING,
        ).exclude(pk=self.pk).exists()
        if opposite_pending_exists:
            raise ValidationError("A pending request already exists between these users.")

    def save(self, *args, **kwargs):
        if self.status != self.Status.PENDING and self.responded_at is None:
            self.responded_at = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)


class Workout(models.Model):
    player = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name="workouts"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_workouts",
    )
    name = models.CharField(max_length=100)
    target_attempts = models.PositiveIntegerField(default=10)   # shots per session
    target_sessions = models.PositiveIntegerField(default=3)   # number of sessions
    goal_percentage = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.player})"

    def clean(self):
        super().clean()

        if not self.assigned_by_id or not self.player_id:
            return

        if self.assigned_by_id == self.player.user_id:
            return

        is_player_coach = CoachProfile.objects.filter(
            user_id=self.assigned_by_id,
            players=self.player,
        ).exists()

        if not is_player_coach:
            raise ValidationError(
                "Workout can only be assigned by the player or one of the player's coaches."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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

        if not self.pk and self.workout.is_completed:
            raise ValidationError("Cannot add session: workout is already completed")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workout.name} - {self.date}"


class WorkoutTemplate(models.Model):
    """Template for quickly creating new workouts with predefined settings"""
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name="workout_templates"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    target_attempts = models.PositiveIntegerField(default=10)  # shots per session
    target_sessions = models.PositiveIntegerField(default=3)   # number of sessions
    goal_percentage = models.FloatField(default=75.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} (Coach: {self.coach.user.username})"


class Notification(models.Model):
    """Notifications for users about various app events"""
    
    class NotificationType(models.TextChoices):
        # Player notifications
        WORKOUT_ASSIGNED = "WORKOUT_ASSIGNED"
        CONNECTION_ACCEPTED = "CONNECTION_ACCEPTED"
        CONNECTION_REQUESTED = "CONNECTION_REQUESTED"
        # Coach notifications
        WORKOUT_COMPLETED = "WORKOUT_COMPLETED"
        SESSION_ADDED = "SESSION_ADDED"
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related objects (optional, for context)
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_initiated_by"
    )
    related_workout = models.ForeignKey(
        Workout,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications"
    )
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class DevicePushToken(models.Model):
    class Platform(models.TextChoices):
        IOS = "ios"
        ANDROID = "android"
        WEB = "web"
        UNKNOWN = "unknown"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_push_tokens",
    )
    expo_push_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.UNKNOWN,
    )
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.platform} - {self.expo_push_token}"
