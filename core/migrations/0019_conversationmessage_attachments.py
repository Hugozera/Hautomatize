from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_anexomensagem_conversation_atualizado_em_conversa_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationmessage',
            name='attachments',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
