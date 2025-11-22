# Generated migration for adding performance indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tutors', '0002_change_vector_dimensions'),
    ]

    operations = [
        # Add indexes on frequently queried fields
        migrations.AddIndex(
            model_name='tutorprofile',
            index=models.Index(fields=['is_verified'], name='tutors_verified_idx'),
        ),
        migrations.AddIndex(
            model_name='tutorprofile',
            index=models.Index(fields=['city'], name='tutors_city_idx'),
        ),
        migrations.AddIndex(
            model_name='tutorprofile',
            index=models.Index(fields=['rating'], name='tutors_rating_idx'),
        ),
        migrations.AddIndex(
            model_name='tutorprofile',
            index=models.Index(fields=['is_premium'], name='tutors_premium_idx'),
        ),
        migrations.AddIndex(
            model_name='tutorprofile',
            index=models.Index(fields=['premium_expires_at'], name='tutors_premium_exp_idx'),
        ),
        migrations.AddIndex(
            model_name='tutorprofile',
            index=models.Index(fields=['stripe_customer_id'], name='tutors_stripe_idx'),
        ),
        migrations.AddIndex(
            model_name='tutorreview',
            index=models.Index(fields=['tutor', 'created_at'], name='reviews_tutor_date_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['category'], name='subjects_category_idx'),
        ),
    ]
