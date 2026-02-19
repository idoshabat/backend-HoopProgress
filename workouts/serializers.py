from rest_framework import serializers
from django.contrib.auth.models import User
from .models import PlayerProfile, Workout, WorkoutSession


class PlayerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerProfile
        fields = ["id", "position", "height_cm"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    position = serializers.ChoiceField(choices=PlayerProfile.Position.choices)
    height_cm = serializers.IntegerField(required=False)

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )

        PlayerProfile.objects.create(
            user=user,
            position=validated_data["position"],
            height_cm=validated_data.get("height_cm"),
        )

        return user


class WorkoutSessionSerializer(serializers.ModelSerializer):
    attempts = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = WorkoutSession
        fields = [
            "id",
            "date",
            "attempts",
            "makes",
            "success_rate",
            "created_at",
            "workout",
        ]
        
    # def validate(self, data):
    #     print("*********",self.instance)
    #     workout = self.instance.workout if self.instance else data.get("workout")

    #     if workout.sessions.count() >= workout.target_sessions:
    #         raise serializers.ValidationError(
    #             "Sessions of a completed workout cannot be modified."
    #         )

    #     return data


class WorkoutSerializer(serializers.ModelSerializer):
    total_attempts = serializers.IntegerField(read_only=True)
    total_makes = serializers.IntegerField(read_only=True)
    average_percentage = serializers.FloatField(read_only=True)
    is_successful = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    num_of_sessions = serializers.IntegerField(read_only=True)
    sessions = WorkoutSessionSerializer(many=True, read_only=True)

    class Meta:
        model = Workout
        fields = [
            "id",
            "name",
            "target_attempts",
            "target_sessions",
            "goal_percentage",
            "num_of_sessions",
            "total_attempts",
            "total_makes",
            "average_percentage",
            "is_completed",
            "is_successful",
            "sessions",
            "created_at",
        ]
        
    def validate(self, data):
        instance = self.instance

        if instance and instance.sessions.count() >= instance.target_sessions:
            raise serializers.ValidationError(
                "Completed workouts cannot be edited."
            )

        return data
