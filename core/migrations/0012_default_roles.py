from django.db import migrations


def create_default_roles(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    from core.permissions import all_permission_codes

    # full administrator role with all permissions
    all_perms = all_permission_codes()
    Role.objects.get_or_create(
        codename='administrador',
        defaults={
            'name': 'Administrador',
            'permissions': ','.join(all_perms),
            'descricao': 'Acesso completo a todas as funcionalidades'
        }
    )

    # role for managing people and roles
    Role.objects.get_or_create(
        codename='gestor_pessoas',
        defaults={
            'name': 'Gestor de Pessoas',
            'permissions': 'pessoa.add,pessoa.edit,role.manage',
            'descricao': 'Gerencia usuários e papéis no sistema'
        }
    )

    # role for managing companies and certificates
    Role.objects.get_or_create(
        codename='gerente_empresas',
        defaults={
            'name': 'Gerente de Empresas',
            'permissions': 'empresa.view,empresa.edit,certificado.manage',
            'descricao': 'Gerencia empresas, certificados e configurações relacionadas'
        }
    )

    # operator role for downloads and conversor
    Role.objects.get_or_create(
        codename='operador',
        defaults={
            'name': 'Operador',
            'permissions': 'download.manage,conversor.use',
            'descricao': 'Realiza operações de download e conversão'
        }
    )

    # read-only visitor
    Role.objects.get_or_create(
        codename='leitor',
        defaults={
            'name': 'Leitor',
            'permissions': 'empresa.view,pessoa.view,conversor.use',
            'descricao': 'Apenas visualizar informações sem alterações'
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_add_banco_field'),
    ]

    operations = [
        migrations.RunPython(create_default_roles),
    ]
