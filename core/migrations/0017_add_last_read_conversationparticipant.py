# Generated manually to add last_read to ConversationParticipant
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_conversation_conversationmessage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationparticipant',
            name='last_read',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
