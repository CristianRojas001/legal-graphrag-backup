from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):
    dependencies = [
        ('legal_graphrag', '0001_initial'),
    ]

    operations = [
        VectorExtension(),
    ]
