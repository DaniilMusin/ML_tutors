import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Order, Application

User = get_user_model()
logger = logging.getLogger(__name__)


class OrderConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for order-specific notifications.
    Connects to channel: order_<order_id>
    """
    
    async def connect(self):
        """
        Connect to order channel.
        """
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.order_group_name = f'order_{self.order_id}'
        
        # Check if user has access to this order
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        
        # Verify user has access to this order (is student or applied tutor)
        has_access = await self.user_has_order_access(user, self.order_id)
        if not has_access:
            await self.close()
            return
        
        # Join order group
        await self.channel_layer.group_add(
            self.order_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial order status
        order_data = await self.get_order_data(self.order_id)
        await self.send(text_data=json.dumps({
            'type': 'order_status',
            'message': 'Connected to order updates',
            'order': order_data
        }))
        
        logger.info(f"User {user.id} connected to order {self.order_id}")

    async def disconnect(self, close_code):
        """
        Leave order group.
        """
        await self.channel_layer.group_discard(
            self.order_group_name,
            self.channel_name
        )
        
        logger.info(f"User disconnected from order {self.order_id}")

    async def receive(self, text_data):
        """
        Receive message from WebSocket.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")

    # Receive message from order group
    async def new_application(self, event):
        """
        Send new application notification to WebSocket.
        """
        await self.send(text_data=json.dumps({
            'type': 'new_application',
            'message': event['message'],
            'application': event['application'],
            'timestamp': event['timestamp']
        }))

    async def application_chosen(self, event):
        """
        Send application chosen notification to WebSocket.
        """
        await self.send(text_data=json.dumps({
            'type': 'application_chosen',
            'message': event['message'],
            'application': event['application'],
            'timestamp': event['timestamp']
        }))

    async def order_status_change(self, event):
        """
        Send order status change notification to WebSocket.
        """
        await self.send(text_data=json.dumps({
            'type': 'order_status_change',
            'message': event['message'],
            'status': event['status'],
            'timestamp': event['timestamp']
        }))

    async def booking_update(self, event):
        """
        Send booking update notification to WebSocket.
        """
        await self.send(text_data=json.dumps({
            'type': 'booking_update',
            'message': event['message'],
            'booking': event['booking'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def user_has_order_access(self, user, order_id):
        """
        Check if user has access to this order.
        """
        try:
            order = Order.objects.get(id=order_id)
            
            # Student who created the order
            if order.student == user:
                return True
            
            # Tutor who applied to the order
            if hasattr(user, 'tutor_profile'):
                if Application.objects.filter(order=order, tutor=user.tutor_profile).exists():
                    return True
            
            return False
            
        except Order.DoesNotExist:
            return False

    @database_sync_to_async
    def get_order_data(self, order_id):
        """
        Get order data for initial status.
        """
        try:
            order = Order.objects.select_related('student', 'subject').get(id=order_id)
            applications = Application.objects.filter(order=order).select_related('tutor__user')
            
            return {
                'id': order.id,
                'title': order.title,
                'status': order.status,
                'applications_count': applications.count(),
                'budget_range': f"{order.budget_min}-{order.budget_max}",
                'created_at': order.created_at.isoformat(),
            }
        except Order.DoesNotExist:
            return None


class TutorNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for tutor-specific notifications.
    Connects to channel: tutor_<user_id>
    """
    
    async def connect(self):
        """
        Connect to tutor notification channel.
        """
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        
        # Check if user is a tutor
        if not await self.is_tutor(user):
            await self.close()
            return
        
        self.tutor_group_name = f'tutor_{user.id}'
        
        # Join tutor group
        await self.channel_layer.group_add(
            self.tutor_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"Tutor {user.id} connected to notifications")

    async def disconnect(self, close_code):
        """
        Leave tutor group.
        """
        user = self.scope['user']
        if user.is_authenticated:
            await self.channel_layer.group_discard(
                self.tutor_group_name,
                self.channel_name
            )
        
        logger.info(f"Tutor disconnected from notifications")

    async def receive(self, text_data):
        """
        Receive message from WebSocket.
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")

    # Receive messages from tutor group
    async def new_order_match(self, event):
        """
        Send new order match notification to tutor.
        """
        await self.send(text_data=json.dumps({
            'type': 'new_order_match',
            'message': event['message'],
            'order': event['order'],
            'match_score': event.get('match_score', 0),
            'timestamp': event['timestamp']
        }))

    async def application_response(self, event):
        """
        Send application response notification to tutor.
        """
        await self.send(text_data=json.dumps({
            'type': 'application_response',
            'message': event['message'],
            'order_id': event['order_id'],
            'status': event['status'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def is_tutor(self, user):
        """
        Check if user is a tutor.
        """
        return hasattr(user, 'tutor_profile')