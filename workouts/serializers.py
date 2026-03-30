from rest_framework import serializers
from .models import ConnectionRequest, PlayerProfile, Workout, WorkoutSession
from django.contrib.auth import get_user_model
from .models import PlayerProfile, CoachProfile

User = get_user_model()


class PlayerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    coaches = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = PlayerProfile
        fields = ["id", "username", "position", "height_cm", "date_of_birth", "coaches"]

class CoachProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    players = PlayerProfileSerializer(many=True, read_only=True)

    class Meta:
        model = CoachProfile
        fields = ["id", "username", "date_of_birth", "players"]

class RegisterSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.Role.choices)

    # Player fields (only required for players)
    position = serializers.ChoiceField(
        choices=PlayerProfile.Position.choices,
        required=False
    )
    height_cm = serializers.IntegerField(required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["username", "password", "role", "position", "height_cm", "date_of_birth"]
        extra_kwargs = {
            "password": {"write_only": True}
        }

    def validate(self, data):
        role = data.get("role")

        if role == User.Role.PLAYER:
            if not data.get("position"):
                raise serializers.ValidationError("Position is required for players")

        return data

    def create(self, validated_data):
        role = validated_data.pop("role")
        position = validated_data.pop("position", None)
        height_cm = validated_data.pop("height_cm", None)
        date_of_birth = validated_data.pop("date_of_birth", None)

        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            role=role
        )

        if role == User.Role.PLAYER:
            PlayerProfile.objects.create(
                user=user,
                position=position,
                height_cm=height_cm,
                date_of_birth=date_of_birth,
            )

        elif role == User.Role.COACH:
            CoachProfile.objects.create(user=user, date_of_birth=date_of_birth)

        return user


class ConnectionRequestSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = [
            "id",
            "sender",
            "sender_username",
            "receiver",
            "receiver_username",
            "status",
            "created_at",
            "responded_at",
        ]
        read_only_fields = fields

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
    player = serializers.PrimaryKeyRelatedField(
        queryset=PlayerProfile.objects.all(),
        required=False,
    )
    total_attempts = serializers.IntegerField(read_only=True)
    total_makes = serializers.IntegerField(read_only=True)
    average_percentage = serializers.FloatField(read_only=True)
    is_successful = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    num_of_sessions = serializers.IntegerField(read_only=True)
    sessions = WorkoutSessionSerializer(many=True, read_only=True)
    assigned_by = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_by_username = serializers.CharField(
        source="assigned_by.username",
        read_only=True,
    )

    class Meta:
        model = Workout
        fields = [
            "id",
            "player",
            "assigned_by",
            "assigned_by_username",
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
        read_only_fields = ["assigned_by", "assigned_by_username"]
        
    def validate(self, data):
        instance = self.instance

        if instance and instance.sessions.count() >= instance.target_sessions:
            raise serializers.ValidationError(
                "Completed workouts cannot be edited."
            )

        if instance and "player" in data and data["player"] != instance.player:
            raise serializers.ValidationError(
                {"player": "Workout player cannot be changed."}
            )

        return data
