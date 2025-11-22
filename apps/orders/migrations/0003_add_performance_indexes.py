# Generated migration for adding performance indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_ai_matches_order_ai_matches_processed'),
    ]

    operations = [
        # Add indexes on frequently queried fields
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['status'], name='orders_status_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['created_at'], name='orders_created_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['student', 'status'], name='orders_student_status_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['subject', 'status'], name='orders_subject_status_idx'),
        ),
        migrations.AddIndex(
            model_name='application',
            index=models.Index(fields=['order', 'is_chosen'], name='apps_order_chosen_idx'),
        ),
        migrations.AddIndex(
            model_name='application',
            index=models.Index(fields=['tutor'], name='apps_tutor_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['status'], name='bookings_status_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['application'], name='bookings_app_idx'),
        ),
        migrations.AddIndex(
            model_name='embeddingcache',
            index=models.Index(fields=['text_hash'], name='embed_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='embeddingcache',
            index=models.Index(fields=['created_at'], name='embed_created_idx'),
        ),
    ]
