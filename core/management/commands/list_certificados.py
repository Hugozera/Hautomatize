from django.core.management.base import BaseCommand
from core.models import Certificado
import win32crypt, win32con
import win32com.client
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import binascii
from datetime import datetime

class Command(BaseCommand):
    help = 'Lista certificados digitais do Windows e salva no banco'

    def handle(self, *args, **options):
        store = win32com.client.Dispatch('CAPICOM.Store')
        store.Open(2, "My", 0)  # 2 = CurrentUser, "My" = Personal
        for cert in store.Certificates:
            thumbprint = cert.Thumbprint
            nome = cert.SubjectName
            validade = cert.ValidToDate
            obj, created = Certificado.objects.update_or_create(
                thumbprint=thumbprint,
                defaults={
                    'nome': nome,
                    'data_validade': validade,
                }
            )
            self.stdout.write(self.style.SUCCESS(f'Certificado: {nome} ({thumbprint})'))
        store.Close()
