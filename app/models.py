# app/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal # Importa Decimal para manejar números con precisión

class Cliente(models.Model):
    """
    Modelo para representar un cliente en la base de datos.
    """
    nombre_empresa = models.CharField(max_length=200, unique=True, verbose_name="Nombre de la Empresa")
    contacto_principal = models.CharField(max_length=200, blank=True, null=True, verbose_name="Contacto Principal")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    # Relación con el modelo User de Django para asignar un cliente a un usuario
    asignado_a = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='clientes_asignados', verbose_name="Asignado a")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        """
        Representación en cadena del objeto Cliente.
        """
        return self.nombre_empresa

    class Meta:
        """
        Metadatos del modelo Cliente.
        """
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_empresa'] # Ordena los clientes por nombre de empresa por defecto

class TodoItem(models.Model):
    """
    Modelo para representar una oportunidad de venta.
    """
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
        """
        Metadatos del modelo TodoItem.
        """
        verbose_name = "Oportunidad de Venta"
        verbose_name_plural = "Oportunidades de Venta"
        ordering = ['-fecha_creacion'] # Ordena por fecha de creación descendente

    def __str__(self):
        """
        Representación en cadena del objeto TodoItem.
        """
        return self.oportunidad

class Cotizacion(models.Model):
    """
    Modelo para representar una cotización.
    Relacionada con un Cliente y contiene los totales.
    """
    # Opciones para el tipo de cotización (Bajanet o Iamet)
    TIPO_COTIZACION_CHOICES = [
        ('Bajanet', 'Bajanet'),
        ('Iamet', 'Iamet'),
    ]
    
    titulo = models.CharField(max_length=255, default="Cotización sin título", verbose_name="Título de la Cotización")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='cotizaciones', verbose_name="Cliente")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    # Nuevo campo para la descripción general de la cotización
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción General de la Cotización")
    # Nuevo campo para un nombre específico para el PDF (opcional, si quieres que sea diferente al título)
    nombre_cotizacion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nombre para el PDF de la Cotización")

    # Campos para los totales de la cotización
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Subtotal")
    iva_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.16'), verbose_name="Tasa de IVA") # Ej. 0.16 para 16%
    iva_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto de IVA")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total")
    moneda = models.CharField(max_length=5, default='USD', verbose_name="Moneda") # Ej. MXN, USD

    # Campo para el tipo de cotización
    tipo_cotizacion = models.CharField(
        max_length=10,
        choices=TIPO_COTIZACION_CHOICES,
        default='Bajanet', # Valor por defecto
        verbose_name="Tipo de Cotización"
    )

    # Usuario que creó la cotización
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Creado por")

    class Meta:
        """
        Metadatos del modelo Cotizacion.
        """
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ['-fecha_creacion'] # Ordena por fecha de creación descendente

    def __str__(self):
        """
        Representación en cadena del objeto Cotizacion.
        """
        return f"Cotización: {self.titulo} para {self.cliente.nombre_empresa} (ID: {self.id})"

class DetalleCotizacion(models.Model):
    """
    Modelo para representar cada línea de producto/servicio dentro de una cotización.
    """
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='detalles', verbose_name="Cotización")
    nombre_producto = models.CharField(max_length=255, verbose_name="Nombre del Producto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")
    # Se corrigió el error de sintaxis en el verbose_name y se añadió el redondeo en get_total_item
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Descuento (%)") # Ej. 5.00 para 5%

    class Meta:
        """
        Metadatos del modelo DetalleCotizacion.
        """
        verbose_name = "Detalle de Cotización"
        verbose_name_plural = "Detalles de Cotización"
        # Puedes añadir un unique_together si un producto no debe repetirse en la misma cotización
        # unique_together = (('cotizacion', 'nombre_producto'),)

    def get_total_item(self):
        """Calcula el total para este ítem de la cotización aplicando el descuento y redondeando a 2 decimales."""
        item_total = self.cantidad * self.precio_unitario
        item_total -= item_total * (self.descuento_porcentaje / Decimal('100.00'))
        return item_total.quantize(Decimal('0.01')) # Redondea a 2 decimales
        
    def __str__(self):
        """
        Representación en cadena del objeto DetalleCotizacion.
        """
        return f"{self.cantidad} x {self.nombre_producto} en Cotización {self.cotizacion.id}"
