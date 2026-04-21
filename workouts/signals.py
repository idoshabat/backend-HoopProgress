"""
Django signals to trigger notifications on various app events
"""
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
import json

from .models import (
    DevicePushToken,
    Notification,
    Workout,
    WorkoutSession,
    ConnectionRequest,
)
from .serializers import NotificationSerializer

User = get_user_model()
channel_layer = get_channel_layer()
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_notification_to_user(user, notification):
    """
    Send a notification to a user via WebSocket
    """
    try:
        room_group_name = f"notifications_{user.id}"
        serialized = NotificationSerializer(notification).data
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                "type": "notification_message",
                "notification": serialized,
            },
        )
    except Exception as e:
        print(f"Error sending notification: {e}")


def build_notification_route(notification):
    if notification.notification_type in {
        Notification.NotificationType.WORKOUT_ASSIGNED,
        Notification.NotificationType.WORKOUT_COMPLETED,
        Notification.NotificationType.SESSION_ADDED,
    } and notification.related_workout_id:
        return {
            "screen": "workout_details",
            "workoutId": notification.related_workout_id,
        }

    if notification.notification_type in {
        Notification.NotificationType.CONNECTION_ACCEPTED,
        Notification.NotificationType.CONNECTION_REQUESTED,
    }:
        return {
            "screen": "connection_requests",
        }

    return {
        "screen": "notifications",
    }


def send_push_notification_to_user(user, notification):
    tokens = list(
        DevicePushToken.objects.filter(user=user, is_active=True).values_list("expo_push_token", flat=True)
    )

    if not tokens:
        return

    data = build_notification_route(notification)

    for token in tokens:
        payload = {
            "to": token,
            "title": notification.title,
            "body": notification.message,
            "sound": "default",
            "data": {
                **data,
                "notificationId": notification.id,
                "notificationType": notification.notification_type,
            },
        }

        req = urllib_request.Request(
            EXPO_PUSH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body)
                expo_data = parsed.get("data", {})

                if expo_data.get("status") == "error" and expo_data.get("details", {}).get("error") == "DeviceNotRegistered":
                    DevicePushToken.objects.filter(expo_push_token=token).update(
                        is_active=False,
                        last_seen_at=timezone.now(),
                    )
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"Error sending Expo push notification: {exc}")


def notify_user(user, notification):
    send_notification_to_user(user, notification)
    send_push_notification_to_user(user, notification)


@receiver(post_save, sender=Workout)
def notify_player_workout_assigned(sender, instance, created, **kwargs):
    """
    Notify a player when a workout is assigned to them
    """
    if not created:
        return
    
    workout = instance
    player_user = workout.player.user
    coach_name = workout.assigned_by.first_name or workout.assigned_by.username
    
    notification = Notification.objects.create(
        user=player_user,
        notification_type=Notification.NotificationType.WORKOUT_ASSIGNED,
        title="New Workout Assigned",
        message=f"Coach {coach_name} assigned you a new workout: {workout.name}",
        related_user=workout.assigned_by,
        related_workout=workout,
    )
    
    notify_user(player_user, notification)


@receiver(post_save, sender=WorkoutSession)
def notify_coach_session_added(sender, instance, created, **kwargs):
    """
    Notify coach when a player completes a workout session
    """
    if not created:
        return
    
    session = instance
    workout = session.workout
    coach = workout.assigned_by
    player_name = workout.player.user.first_name or workout.player.user.username
    
    if coach:
        notification = Notification.objects.create(
            user=coach,
            notification_type=Notification.NotificationType.SESSION_ADDED,
            title="New Session Completed",
            message=f"Player {player_name} completed a session for workout {workout.name}",
            related_user=workout.player.user,
            related_workout=workout,
        )
        
        notify_user(coach, notification)


@receiver(post_save, sender=Workout)
def notify_coach_workout_completed(sender, instance, created, **kwargs):
    """
    Notify coach when a workout is fully completed by a player
    """
    if created:
        return
    
    workout = instance
    
    # Check if workout just became completed
    if workout.is_completed and not kwargs.get("previous_is_completed"):
        coach = workout.assigned_by
        player_name = workout.player.user.first_name or workout.player.user.username
        
        if coach:
            notification = Notification.objects.create(
                user=coach,
                notification_type=Notification.NotificationType.WORKOUT_COMPLETED,
                title="Workout Completed",
                message=f"Player {player_name} completed the workout {workout.name}!",
                related_user=workout.player.user,
                related_workout=workout,
            )
            
            notify_user(coach, notification)


@receiver(post_save, sender=ConnectionRequest)
def notify_connection_request_status(sender, instance, created, **kwargs):
    """
    Notify users about connection request status changes
    """
    request = instance
    
    if created:
        # Notify receiver about new connection request
        notification = Notification.objects.create(
            user=request.receiver,
            notification_type=Notification.NotificationType.CONNECTION_REQUESTED,
            title="New Connection Request",
            message=f"{request.sender.first_name or request.sender.username} wants to connect with you",
            related_user=request.sender,
        )
        notify_user(request.receiver, notification)
    
    else:
        # Notify sender about connection request response
        if request.status == ConnectionRequest.Status.ACCEPTED:
            notification = Notification.objects.create(
                user=request.sender,
                notification_type=Notification.NotificationType.CONNECTION_ACCEPTED,
                title="Connection Accepted",
                message=f"{request.receiver.first_name or request.receiver.username} accepted your connection request",
                related_user=request.receiver,
            )
            notify_user(request.sender, notification)
