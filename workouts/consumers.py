import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Notification
from .serializers import NotificationSerializer

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Allows users to receive notifications as they are created.
    """

    async def connect(self):
        """Handle new WebSocket connections"""
        self.user = self.scope.get("user")
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        # Create a unique room name for this user's notifications
        self.room_name = f"notifications_{self.user.id}"
        self.room_group_name = f"notifications_{self.user.id}"
        
        # Join the notification group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "unread_count": unread_count,
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnections"""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            
            if message_type == "mark_as_read":
                notification_id = data.get("notification_id")
                await self.mark_notification_as_read(notification_id)
                
            elif message_type == "fetch_notifications":
                notifications = await self.get_user_notifications()
                await self.send(text_data=json.dumps({
                    "type": "notifications_list",
                    "notifications": notifications,
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Invalid JSON",
            }))

    async def notification_message(self, event):
        """Handle notification events from the group"""
        notification_data = event["notification"]
        
        await self.send(text_data=json.dumps({
            "type": "new_notification",
            "notification": notification_data,
        }))

    async def read_notification_message(self, event):
        """Handle notification read event"""
        notification_id = event["notification_id"]
        
        await self.send(text_data=json.dumps({
            "type": "notification_read",
            "notification_id": notification_id,
        }))

    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread notifications for the user"""
        return self.user.notifications.filter(is_read=False).count()

    @database_sync_to_async
    def get_user_notifications(self):
        """Get all notifications for the user"""
        notifications = self.user.notifications.all()[:50]  # Limit to last 50
        serializer = NotificationSerializer(notifications, many=True)
        return serializer.data

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Mark a specific notification as read"""
        try:
            notification = self.user.notifications.get(id=notification_id)
            notification.mark_as_read()
        except Notification.DoesNotExist:
            pass
