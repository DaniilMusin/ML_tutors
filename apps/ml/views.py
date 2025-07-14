from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.cache import cache
import hashlib
import json

from apps.orders.models import Order
from .services import AIMatchingService


class MatchView(APIView):
    """
    AI-powered tutor matching for orders.
    POST /api/ml/match/ with order_id → returns top-k tutor matches with LLM rerank.
    """
    permission_classes = [IsAuthenticated]
    
    def __init__(self):
        super().__init__()
        self.ai_service = AIMatchingService()
    
    def post(self, request):
        """
        Get AI-powered tutor matches for an order.
        """
        order_id = request.data.get('order_id')
        if not order_id:
            return Response(
                {'error': 'order_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get order
        try:
            order = get_object_or_404(Order, id=order_id, student=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check cache first
        cache_key = self._get_cache_key(order_id, request.data)
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response(cached_result)
        
        try:
            # Get AI matches using ranker.get_top_k() + OpenAI rerank
            limit = request.data.get('limit', 3)
            matches = self.ai_service.get_ai_matches(order, limit=limit)
            
            result = {
                'order_id': order_id,
                'matches': matches,
                'total_found': len(matches),
                'cached': False
            }
            
            # Cache result for 1 hour
            cache.set(cache_key, result, 3600)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'AI matching failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_cache_key(self, order_id, request_data):
        """Generate cache key for Redis."""
        cache_data = {
            'order_id': order_id,
            'limit': request_data.get('limit', 3)
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return f"ai_match:{hashlib.md5(cache_string.encode()).hexdigest()}"