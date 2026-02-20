# Generated manual migration to add LayoutBancario model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_agendamento_options_tarefadownload'),
    ]

    operations = [
        migrations.CreateModel(
            name='LayoutBancario',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
                ('identificadores', models.TextField(blank=True)),
                ('template_html', models.TextField(blank=True)),
                ('exemplo_pdf', models.FileField(blank=True, null=True, upload_to='conversor/layout_examples/')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('ativo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Layout Bancário',
                'verbose_name_plural': 'Layouts Bancários',
            },
        ),
    ]
