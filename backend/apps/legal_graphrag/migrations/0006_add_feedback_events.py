from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('legal_graphrag', '0005_add_fts_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnswerFeedbackEvent',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user_id', models.CharField(blank=True, max_length=128, null=True)),
                ('session_id', models.CharField(blank=True, max_length=128, null=True)),
                ('conversation_id', models.CharField(blank=True, max_length=128, null=True)),
                ('message_id', models.CharField(max_length=128)),
                ('answer_hash', models.CharField(blank=True, max_length=64, null=True)),
                ('event_type', models.CharField(choices=[('vote', 'vote'), ('copy', 'copy')], max_length=16)),
                ('vote_value', models.SmallIntegerField(blank=True, null=True)),
                ('route', models.CharField(blank=True, max_length=255, null=True)),
                ('app_version', models.CharField(blank=True, max_length=64, null=True)),
                ('model', models.CharField(blank=True, max_length=64, null=True)),
            ],
            options={
                'db_table': 'answer_feedback_events',
            },
        ),
        migrations.AddIndex(
            model_name='answerfeedbackevent',
            index=models.Index(fields=['message_id'], name='idx_feedback_message_id'),
        ),
        migrations.AddIndex(
            model_name='answerfeedbackevent',
            index=models.Index(fields=['created_at'], name='idx_feedback_created_at'),
        ),
        migrations.AddIndex(
            model_name='answerfeedbackevent',
            index=models.Index(fields=['session_id'], name='idx_feedback_session'),
        ),
        migrations.AddConstraint(
            model_name='answerfeedbackevent',
            constraint=models.CheckConstraint(
                check=Q(event_type__in=['vote', 'copy']),
                name='feedback_event_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='answerfeedbackevent',
            constraint=models.CheckConstraint(
                check=Q(vote_value__in=[-1, 1]) | Q(vote_value__isnull=True),
                name='feedback_vote_value_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='answerfeedbackevent',
            constraint=models.CheckConstraint(
                check=Q(event_type='vote', vote_value__isnull=False) | Q(event_type='copy'),
                name='feedback_vote_requires_value',
            ),
        ),
    ]
