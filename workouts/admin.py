from django.contrib import admin
from .models import CoachProfile, ConnectionRequest, PlayerProfile, User, Workout, WorkoutSession

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id","username", "email", "role", "is_staff", "is_superuser")


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "position", "height_cm", "date_of_birth", "created_at")
    list_filter = ("position", "created_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-created_at",)
    
@admin.register(CoachProfile)
class CoachProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "date_of_birth", "created_at")


@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "status", "created_at", "responded_at")
    list_filter = ("status", "created_at")
    search_fields = ("sender__username", "receiver__username")

# Optional: Register workouts if you want
@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("name", "player", "assigned_by", "created_at")
    search_fields = ("name", "player__user__username", "assigned_by__username")
    ordering = ("-created_at",)

@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ("workout","id", "date", "attempts", "makes", "success_rate", "created_at")
    list_filter = ("workout__name", "date")
    search_fields = ("workout__name", "workout__player__user__username")
    ordering = ("-date",)

