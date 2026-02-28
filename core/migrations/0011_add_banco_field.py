from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_empresa_ultimo_zip"),
    ]

    operations = [
        migrations.AddField(
            model_name="arquivoconversao",
            name="banco",
            field=models.CharField(max_length=50, blank=True, default=""),
        ),
    ]
