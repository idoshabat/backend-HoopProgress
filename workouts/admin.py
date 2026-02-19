from django.contrib import admin
from .models import PlayerProfile, Workout, WorkoutSession

# Register PlayerProfile
@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "position", "height_cm", "created_at")
    list_filter = ("position", "created_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-created_at",)

# Optional: Register workouts if you want
@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("name", "player", "created_at")
    search_fields = ("name", "player__user__username")
    ordering = ("-created_at",)

@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ("workout","id", "date", "attempts", "makes", "success_rate", "created_at")
    list_filter = ("workout__name", "date")
    search_fields = ("workout__name", "workout__player__user__username")
    ordering = ("-date",)
