from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('painel', '0005_alter_chatmessage_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='analista',
            name='disponivel_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
