from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_alter_arquivoconversao_banco_siegcredential'),
    ]

    operations = [
        migrations.DeleteModel(
            name='SiegCredential',
        ),
    ]
