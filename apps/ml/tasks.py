"""
Celery tasks for ML operations.
"""
import logging
from celery import shared_task
from django.db import transaction

from apps.orders.models import Order
from apps.ml.services import AIMatchingService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def process_order_matching(self, order_id: int):
    """
    Process AI matching for a specific order with idempotency.

    Args:
        order_id: ID of the order to process

    Returns:
        dict: Processing result with status and match count
    """
    try:
        # Use atomic transaction with select_for_update for idempotency
        with transaction.atomic():
            # Lock the order row to prevent concurrent processing
            order = Order.objects.select_for_update(nowait=False).get(id=order_id)

            # Idempotency check - skip if already processed
            if order.ai_matches_processed:
                logger.info(f"Order {order_id} already processed (idempotency check), skipping")
                return {
                    'status': 'skipped',
                    'reason': 'already_processed',
                    'order_id': order_id
                }

            # Validate order is in valid state for matching
            if order.status not in ['open', 'pending']:
                logger.warning(f"Order {order_id} has status {order.status}, skipping AI matching")
                return {
                    'status': 'skipped',
                    'reason': f'invalid_status_{order.status}',
                    'order_id': order_id
                }

            # Get AI matches
            matching_service = AIMatchingService()
            matches = matching_service.get_ai_matches(order, limit=5)

            # Update order with matches atomically
            order.ai_matches = matches
            order.ai_matches_processed = True
            order.save(update_fields=['ai_matches', 'ai_matches_processed'])

            logger.info(f"Successfully processed AI matches for order {order_id}: {len(matches)} matches found")

            return {
                'status': 'success',
                'order_id': order_id,
                'match_count': len(matches)
            }

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        # Don't retry for missing orders
        return {
            'status': 'error',
            'reason': 'order_not_found',
            'order_id': order_id
        }

    except Exception as exc:
        logger.error(f"Error processing order {order_id}: {exc}", exc_info=True)
        # Let Celery handle retries automatically with backoff
        raise


@shared_task
def cleanup_old_embeddings():
    """
    Clean up old embedding cache entries.
    """
    try:
        from apps.orders.models import EmbeddingCache
        from django.utils import timezone
        from datetime import timedelta
        
        # Delete embeddings older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = EmbeddingCache.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old embedding cache entries")
        
    except Exception as exc:
        logger.error(f"Error cleaning up embeddings: {exc}")
        raise


@shared_task
def retrain_matching_model():
    """
    Retrain the LightGBM matching model.
    """
    try:
        from apps.ml.management.commands.train_ranker import Command
        
        # Run the training command
        command = Command()
        command.handle()
        
        logger.info("Successfully retrained matching model")
        
    except Exception as exc:
        logger.error(f"Error retraining model: {exc}")
        raise


@shared_task
def update_tutor_embeddings():
    """
    Update embeddings for all tutor profiles.
    """
    try:
        from apps.tutors.models import TutorProfile
        from apps.ml.services import AIMatchingService
        
        matching_service = AIMatchingService()
        tutors = TutorProfile.objects.filter(is_verified=True)
        
        updated_count = 0
        for tutor in tutors:
            try:
                # Generate embedding for tutor bio
                if tutor.bio:
                    embedding = matching_service._get_embedding(tutor.bio)
                    if embedding:
                        tutor.vector = embedding
                        tutor.save(update_fields=['vector'])
                        updated_count += 1
                        
            except Exception as e:
                logger.warning(f"Failed to update embedding for tutor {tutor.id}: {e}")
                continue
        
        logger.info(f"Updated embeddings for {updated_count} tutors")
        
    except Exception as exc:
        logger.error(f"Error updating tutor embeddings: {exc}")
        raise
