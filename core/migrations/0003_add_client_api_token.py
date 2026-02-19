# Generated migration to add client_api_token to Pessoa
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_agendamento_options_alter_empresa_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pessoa',
            name='client_api_token',
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
    ]
