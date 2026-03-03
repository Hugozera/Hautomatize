"""
Django management command to migrate Empresas from db.sqlite3 to db_prod.sqlite3
"""
import sqlite3
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Empresa, Pessoa
from django.db import transaction
from pathlib import Path


class Command(BaseCommand):
    help = 'Migrate empresas from db.sqlite3 to db_prod.sqlite3'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-db',
            type=str,
            default='db.sqlite3',
            help='Source database file (default: db.sqlite3)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip empresas that already exist in the target database'
        )

    def handle(self, *args, **options):
        source_db = options['source_db']
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']

        # Get absolute path
        base_dir = Path(settings.BASE_DIR)
        source_path = base_dir / source_db
        
        if not source_path.exists():
            self.stdout.write(self.style.ERROR(f'Source database not found: {source_path}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Source database: {source_path}'))
        self.stdout.write(self.style.SUCCESS(f'Target database: {settings.DATABASES["default"]["NAME"]}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Connect to source database
        conn = sqlite3.connect(str(source_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Check what columns exist in source database
            cursor.execute("PRAGMA table_info(core_empresa)")
            existing_columns = [col[1] for col in cursor.fetchall()]
            self.stdout.write(f'Available columns in source: {", ".join(existing_columns)}')
            
            # Build dynamic query based on available columns
            select_columns = []
            for col in ['cnpj', 'razao_social', 'nome_fantasia', 'inscricao_municipal',
                       'inscricao_estadual', 'tipo', 'ativo', 'cep', 'logradouro', 'numero',
                       'complemento', 'bairro', 'municipio', 'uf', 'certificado_thumbprint',
                       'certificado_senha', 'certificado_validade', 'certificado_emitente',
                       'certificado_antigo', 'data_cadastro', 'ultimo_download']:
                if col in existing_columns:
                    select_columns.append(col)
            
            query = f"SELECT {', '.join(select_columns)} FROM core_empresa ORDER BY id"
            cursor.execute(query)
            
            empresas_data = cursor.fetchall()
            total = len(empresas_data)
            
            self.stdout.write(f'\nFound {total} empresas in source database')

            if total == 0:
                self.stdout.write(self.style.WARNING('No empresas to migrate'))
                return

            created = 0
            updated = 0
            skipped = 0
            errors = 0

            with transaction.atomic():
                for row in empresas_data:
                    cnpj = row['cnpj']
                    
                    # Helper function to safely get column value
                    def get_value(col_name, default=''):
                        try:
                            return row[col_name] if col_name in select_columns else default
                        except (KeyError, IndexError):
                            return default
                    
                    try:
                        # Check if empresa already exists
                        exists = Empresa.objects.filter(cnpj=cnpj).exists()
                        
                        if exists:
                            if skip_existing:
                                self.stdout.write(f'  Skipping existing: {cnpj} - {get_value("nome_fantasia")}')
                                skipped += 1
                                continue
                            else:
                                if not dry_run:
                                    # Update existing
                                    empresa = Empresa.objects.get(cnpj=cnpj)
                                    empresa.razao_social = get_value('razao_social')
                                    empresa.nome_fantasia = get_value('nome_fantasia')
                                    empresa.inscricao_municipal = get_value('inscricao_municipal')
                                    empresa.inscricao_estadual = get_value('inscricao_estadual')
                                    empresa.tipo = get_value('tipo', 'matriz')
                                    empresa.ativo = bool(get_value('ativo', 1))
                                    empresa.cep = get_value('cep')
                                    empresa.logradouro = get_value('logradouro')
                                    empresa.numero = get_value('numero')
                                    empresa.complemento = get_value('complemento')
                                    empresa.bairro = get_value('bairro')
                                    empresa.municipio = get_value('municipio')
                                    empresa.uf = get_value('uf')
                                    empresa.certificado_thumbprint = get_value('certificado_thumbprint')
                                    empresa.certificado_senha = get_value('certificado_senha')
                                    empresa.certificado_validade = get_value('certificado_validade', None)
                                    empresa.certificado_emitente = get_value('certificado_emitente')
                                    empresa.certificado_antigo = bool(get_value('certificado_antigo', 0))
                                    empresa.save()
                                    self.stdout.write(f'  Updated: {cnpj} - {get_value("nome_fantasia")}')
                                else:
                                    self.stdout.write(f'  Would update: {cnpj} - {get_value("nome_fantasia")}')
                                updated += 1
                        else:
                            if not dry_run:
                                # Create new empresa
                                empresa = Empresa(
                                    cnpj=cnpj,
                                    razao_social=get_value('razao_social'),
                                    nome_fantasia=get_value('nome_fantasia'),
                                    inscricao_municipal=get_value('inscricao_municipal'),
                                    inscricao_estadual=get_value('inscricao_estadual'),
                                    tipo=get_value('tipo', 'matriz'),
                                    ativo=bool(get_value('ativo', 1)),
                                    cep=get_value('cep'),
                                    logradouro=get_value('logradouro'),
                                    numero=get_value('numero'),
                                    complemento=get_value('complemento'),
                                    bairro=get_value('bairro'),
                                    municipio=get_value('municipio'),
                                    uf=get_value('uf'),
                                    certificado_thumbprint=get_value('certificado_thumbprint'),
                                    certificado_senha=get_value('certificado_senha'),
                                    certificado_validade=get_value('certificado_validade', None),
                                    certificado_emitente=get_value('certificado_emitente'),
                                    certificado_antigo=bool(get_value('certificado_antigo', 0)),
                                    # Note: certificado_arquivo and ultimo_zip are FileFields
                                    # and would need special handling if migration is needed
                                )
                                empresa.save()
                                self.stdout.write(f'  Created: {cnpj} - {get_value("nome_fantasia")}')
                            else:
                                self.stdout.write(f'  Would create: {cnpj} - {get_value("nome_fantasia")}')
                            created += 1
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  Error with {cnpj}: {str(e)}'))
                        errors += 1
                        continue

                if dry_run:
                    # Rollback the transaction on dry run
                    transaction.set_rollback(True)

            # Print summary
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS('MIGRATION SUMMARY'))
            self.stdout.write('='*50)
            self.stdout.write(f'Total empresas found: {total}')
            self.stdout.write(self.style.SUCCESS(f'Created: {created}'))
            self.stdout.write(self.style.WARNING(f'Updated: {updated}'))
            self.stdout.write(f'Skipped: {skipped}')
            if errors > 0:
                self.stdout.write(self.style.ERROR(f'Errors: {errors}'))
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
            else:
                self.stdout.write(self.style.SUCCESS('\nMigration completed successfully!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during migration: {str(e)}'))
            import traceback
            traceback.print_exc()
        finally:
            conn.close()
