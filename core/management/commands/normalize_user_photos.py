"""
Management command para normalizar todas as fotos dos usuários.
Redimensiona fotos antigas que ainda não foram processadas pelo novo sistema.
"""
from django.core.management.base import BaseCommand
from core.models import Pessoa
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os


class Command(BaseCommand):
    help = 'Redimensiona todas as fotos dos usuários para 300x300px máximo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força o redimensionamento mesmo de fotos já processadas',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        pessoas_com_foto = Pessoa.objects.filter(foto__isnull=False).exclude(foto='')
        
        total = pessoas_com_foto.count()
        processadas = 0
        erros = 0
        
        self.stdout.write(f'Total de pessoas com foto: {total}')
        
        for pessoa in pessoas_com_foto:
            try:
                # Verifica se já foi redimensionada (tamanho menor que limite)
                if not force:
                    img = Image.open(pessoa.foto.file)
                    max_size = (300, 300)
                    if img.size[0] <= max_size[0] and img.size[1] <= max_size[1]:
                        continue  # Já está no tamanho correto
                
                # Redimensiona
                self._resize_image(pessoa)
                processadas += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {pessoa.user.username} ({pessoa.pk})')
                )
            except Exception as e:
                erros += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ {pessoa.user.username} ({pessoa.pk}): {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Processo concluído!')
        )
        self.stdout.write(f'Processadas: {processadas}')
        self.stdout.write(f'Erros: {erros}')
    
    def _resize_image(self, pessoa):
        """Redimensiona a imagem para máximo de 300x300px."""
        try:
            img = Image.open(pessoa.foto.file)
            
            # Limite máximo
            max_size = (300, 300)
            
            # Se imagem é maior que o limite, redimensionar
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Converter para RGB se for PNG com alpha
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        rgb_img.paste(img, mask=img.split()[-1])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img
                
                # Salvar em BytesIO
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=85, optimize=True)
                img_io.seek(0)
                
                # Substituir arquivo
                filename = os.path.splitext(pessoa.foto.name)[0] + '.jpg'
                pessoa.foto.save(
                    filename,
                    ContentFile(img_io.read()),
                    save=True
                )
        except Exception:
            raise
