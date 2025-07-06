# app/admin.py

from django.contrib import admin
from .models import Cliente, TodoItem # Importa TodoItem en lugar de Cotizacion/ItemCotizacion
from django.contrib.auth.models import User # Necesario si usas el modelo User en el admin

# Registra el modelo Cliente en el panel de administración
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """
    Configuración para el modelo Cliente en el panel de administración de Django.
    """
    # Campos que se mostrarán en la lista de clientes
    list_display = ('nombre_empresa', 'email', 'telefono', 'asignado_a') # 'fecha_creacion' eliminado
    # Campos por los cuales se puede buscar
    search_fields = ('nombre_empresa', 'email', 'telefono')
    # Campos por los cuales se puede filtrar la lista
    list_filter = ('asignado_a',) # 'fecha_creacion' eliminado
    # No hay date_hierarchy para Cliente ya que no tiene campo de fecha_creacion directo

# Registra el modelo TodoItem (Oportunidad de Venta) en el panel de administración
@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    """
    Configuración para el modelo TodoItem (Oportunidad de Venta) en el panel de administración de Django.
    """
    # Campos que se mostrarán en la lista de oportunidades de venta
    list_display = (
        'oportunidad', 'cliente', 'monto', 'probabilidad_cierre', 
        'mes_cierre', 'get_area_display', 'get_producto_display', 
        'usuario', 'fecha_creacion', 'fecha_actualizacion'
    )
    # Campos por los cuales se puede buscar
    search_fields = (
        'oportunidad', 'contacto', 'cliente__nombre_empresa', 
        'area', 'producto'
    )
    # Campos por los cuales se puede filtrar la lista
    list_filter = (
        'area', 'producto', 'mes_cierre', 'probabilidad_cierre', 
        'cliente', 'usuario'
    )
    # Permite navegar por fechas de creación
    date_hierarchy = 'fecha_creacion'
    
    # Campos de solo lectura (no se pueden editar directamente en el admin)
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')

    # Sobreescribe el método save_model para asignar automáticamente el usuario creador
    def save_model(self, request, obj, form, change):
        """
        Asigna el usuario que está logueado como 'usuario' (creador)
        al crear una nueva oportunidad de venta.
        """
        if not obj.pk: # Si es una nueva oportunidad (no tiene PK aún)
            obj.usuario = request.user # Asigna el usuario actual
        super().save_model(request, obj, form, change)

    # Puedes añadir un método para mostrar el monto con formato si lo deseas,
    # aunque el filtro 'format_currency_es' se usa en los templates.
    # Para el admin, el list_display ya muestra el campo 'monto' directamente.
    # Si necesitas un formato específico en el admin, podrías hacer algo como:
    # def formatted_monto(self, obj):
    #     return f"${obj.monto:,.2f}" # Formato simple de Python
    # formatted_monto.short_description = "Monto"
    # Y luego usar 'formatted_monto' en list_display en lugar de 'monto'.
