"""
Django signals to trigger notifications on various app events
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import json

from .models import (
    Notification,
    Workout,
    WorkoutSession,
    ConnectionRequest,
)
from .serializers import NotificationSerializer

User = get_user_model()
channel_layer = get_channel_layer()


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
    
    send_notification_to_user(player_user, notification)


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
        
        send_notification_to_user(coach, notification)


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
            
            send_notification_to_user(coach, notification)


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
        send_notification_to_user(request.receiver, notification)
    
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
            send_notification_to_user(request.sender, notification)
