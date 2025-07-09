import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cartera_clientes.settings')
django.setup()

from app.models import TodoItem
from django.utils import timezone

# Corregir registros con fechas corruptas usando la fecha actual
corregidos = 0
for item in TodoItem.objects.all():
    try:
        # Si alguna fecha es nula, vacía o mal formateada, se corrige
        actualizar = False
        if not item.fecha_creacion or str(item.fecha_creacion).strip() in ('', '0000-00-00 00:00:00'):
            item.fecha_creacion = timezone.now()
            actualizar = True
        if not item.fecha_actualizacion or str(item.fecha_actualizacion).strip() in ('', '0000-00-00 00:00:00'):
            item.fecha_actualizacion = timezone.now()
            actualizar = True
        # Intenta parsear, si falla, corrige
        try:
            str_fecha_creacion = str(item.fecha_creacion)
            datetime.strptime(str_fecha_creacion[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            item.fecha_creacion = timezone.now()
            actualizar = True
        try:
            str_fecha_actualizacion = str(item.fecha_actualizacion)
            datetime.strptime(str_fecha_actualizacion[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            item.fecha_actualizacion = timezone.now()
            actualizar = True
        if actualizar:
            item.save()
            corregidos += 1
    except Exception:
        continue
print(f"Registros corregidos: {corregidos}")
