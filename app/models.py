# cartera_clientes/app/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Cliente(models.Model):
    nombre_empresa = models.CharField(max_length=200, unique=True, verbose_name="Nombre de la Empresa")
    contacto_principal = models.CharField(max_length=200, blank=True, null=True, verbose_name="Contacto Principal")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    asignado_a = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='clientes_asignados', verbose_name="Asignado a")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return self.nombre_empresa

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_empresa']

class TodoItem(models.Model):
    # Opciones para el campo 'area'
    AREA_CHOICES = [
        ('SISTEMAS', 'Sistemas'),
        ('Recursos Humanos', 'Recursos Humanos'),
        ('Compras', 'Compras'),
        ('Seguridad', 'Seguridad'),
        ('Mantenimiento', 'Mantenimiento'),
        ('Almacén', 'Almacén'),
    ]

    # Opciones para el campo 'producto'
    PRODUCTO_CHOICES = [
        ('ZEBRA', 'ZEBRA'),
        ('AXIS', 'AXIS'),
        ('AVIGILION', 'AVIGILION'),
        ('CISCO', 'CISCO'),
        ('GENETEC', 'GENETEC'),
        ('SOFTWARE', 'SOFTWARE'),
        ('SERVICIOS', 'SERVICIOS'),
        ('PÓLIZA', 'PÓLIZA'),
        ('RUNRATE', 'RUNRATE'),
    ]

    # Opciones para el campo 'mes_cierre'
    MES_CHOICES = [
        ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'), ('04', 'Abril'),
        ('05', 'Mayo'), ('06', 'Junio'), ('07', 'Julio'), ('08', 'Agosto'),
        ('09', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ]

    # 'usuario' es el campo que vincula la oportunidad con el usuario que la creó/posee
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='oportunidades')
    oportunidad = models.CharField(max_length=200, verbose_name="Oportunidad de Venta")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='oportunidades', verbose_name="Cliente")
    contacto = models.CharField(max_length=100, verbose_name="Contacto del Cliente")
    producto = models.CharField(max_length=100, choices=PRODUCTO_CHOICES, verbose_name="Producto / Servicio")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto de la Oportunidad")
    probabilidad_cierre = models.IntegerField(verbose_name="Probabilidad de Cierre (%)")
    mes_cierre = models.CharField(max_length=2, choices=MES_CHOICES, verbose_name="Mes de Cierre Esperado")
    area = models.CharField(max_length=50, choices=AREA_CHOICES, verbose_name="Área")
    comentarios = models.TextField(blank=True, null=True, verbose_name="Comentarios")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Oportunidad de Venta"
        verbose_name_plural = "Oportunidades de Venta"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.oportunidad
