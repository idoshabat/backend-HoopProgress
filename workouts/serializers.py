from rest_framework import serializers
from .models import ConnectionRequest, DevicePushToken, PlayerProfile, Workout, WorkoutSession, WorkoutTemplate
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import PlayerProfile, CoachProfile

User = get_user_model()


class PlayerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", required=False)
    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)
    phone_number = serializers.CharField(source="user.phone_number", required=False, allow_blank=True)
    coaches = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = PlayerProfile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "position",
            "height_cm",
            "date_of_birth",
            "profile_photo_url",
            "profile_photo_public_id",
            "coaches",
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        user = instance.user
        if "first_name" in user_data:
            user.first_name = user_data["first_name"]
        if "last_name" in user_data:
            user.last_name = user_data["last_name"]
        if "email" in user_data:
            user.email = user_data["email"]
        if "phone_number" in user_data:
            user.phone_number = user_data["phone_number"]
        user.save(update_fields=["first_name", "last_name", "email", "phone_number"])

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not request or request.user != instance.user:
            data.pop("phone_number", None)
        return data

class CoachProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", required=False)
    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)
    phone_number = serializers.CharField(source="user.phone_number", required=False, allow_blank=True)
    players = PlayerProfileSerializer(many=True, read_only=True)

    class Meta:
        model = CoachProfile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "profile_photo_url",
            "profile_photo_public_id",
            "players",
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        user = instance.user
        if "first_name" in user_data:
            user.first_name = user_data["first_name"]
        if "last_name" in user_data:
            user.last_name = user_data["last_name"]
        if "email" in user_data:
            user.email = user_data["email"]
        if "phone_number" in user_data:
            user.phone_number = user_data["phone_number"]
        user.save(update_fields=["first_name", "last_name", "email", "phone_number"])

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not request or request.user != instance.user:
            data.pop("phone_number", None)
        return data

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=User.Role.choices)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)

    # Player fields (only required for players)
    position = serializers.ChoiceField(
        choices=PlayerProfile.Position.choices,
        required=False
    )
    height_cm = serializers.IntegerField(required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    profile_photo_url = serializers.URLField(required=False, allow_null=True)
    profile_photo_public_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "position",
            "height_cm",
            "date_of_birth",
            "profile_photo_url",
            "profile_photo_public_id",
        ]
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
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        phone_number = validated_data.pop("phone_number", "")
        email = validated_data.pop("email", "").strip().lower()
        position = validated_data.pop("position", None)
        height_cm = validated_data.pop("height_cm", None)
        date_of_birth = validated_data.pop("date_of_birth", None)
        profile_photo_url = validated_data.pop("profile_photo_url", None)
        profile_photo_public_id = validated_data.pop("profile_photo_public_id", None)

        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            email=email,
            role=role,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
        )

        if role == User.Role.PLAYER:
            player_profile_kwargs = {
                "user": user,
                "position": position,
                "profile_photo_url": profile_photo_url,
                "profile_photo_public_id": profile_photo_public_id,
            }

            if height_cm is not None:
                player_profile_kwargs["height_cm"] = height_cm

            if date_of_birth is not None:
                player_profile_kwargs["date_of_birth"] = date_of_birth

            PlayerProfile.objects.create(
                **player_profile_kwargs,
            )

        elif role == User.Role.COACH:
            coach_profile_kwargs = {
                "user": user,
                "profile_photo_url": profile_photo_url,
                "profile_photo_public_id": profile_photo_public_id,
            }
            if date_of_birth is not None:
                coach_profile_kwargs["date_of_birth"] = date_of_birth

            CoachProfile.objects.create(**coach_profile_kwargs)

        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


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
    workout_name = serializers.CharField(source="workout.name", read_only=True)
    workout_goal_percentage = serializers.FloatField(
        source="workout.goal_percentage",
        read_only=True,
    )
    player_username = serializers.CharField(
        source="workout.player.user.username",
        read_only=True,
    )

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
            "workout_name",
            "workout_goal_percentage",
            "player_username",
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

        if instance:
            existing_sessions = instance.sessions.count()

            if existing_sessions >= instance.target_sessions:
                raise serializers.ValidationError(
                    "Completed workouts cannot be edited."
                )

            next_target_sessions = data.get("target_sessions", instance.target_sessions)
            if next_target_sessions < existing_sessions:
                raise serializers.ValidationError(
                    {
                        "target_sessions": (
                            f"Target sessions cannot be less than completed sessions ({existing_sessions})."
                        )
                    }
                )

        if instance and "player" in data and data["player"] != instance.player:
            raise serializers.ValidationError(
                {"player": "Workout player cannot be changed."}
            )

        return data


class WorkoutTemplateSerializer(serializers.ModelSerializer):
    coach_username = serializers.CharField(source="coach.user.username", read_only=True)
    
    class Meta:
        model = WorkoutTemplate
        fields = [
            "id",
            "coach",
            "coach_username",
            "name",
            "description",
            "target_attempts",
            "target_sessions",
            "goal_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["coach", "coach_username", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    related_user_username = serializers.CharField(
        source="related_user.username",
        read_only=True,
        required=False
    )
    related_workout_name = serializers.CharField(
        source="related_workout.name",
        read_only=True,
        required=False
    )

    class Meta:
        from .models import Notification
        model = Notification
        fields = [
            "id",
            "user",
            "notification_type",
            "title",
            "message",
            "related_user",
            "related_user_username",
            "related_workout",
            "related_workout_name",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "read_at",
        ]


class DevicePushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevicePushToken
        fields = [
            "id",
            "expo_push_token",
            "platform",
            "is_active",
            "last_seen_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "last_seen_at",
            "created_at",
        ]
        extra_kwargs = {
            "expo_push_token": {"validators": []},
        }
