from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('painel', '0003_add_atendimentoanexo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atendimento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensagens', to='painel.atendimento')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
            ],
            options={
                'verbose_name': 'Mensagem de Chat',
                'verbose_name_plural': 'Mensagens de Chat',
                'ordering': ['criado_em'],
            },
        ),
    ]
