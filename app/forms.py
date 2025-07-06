from django import forms
from .models import TodoItem, Cliente
from django.contrib.auth.models import User

class VentaForm(forms.ModelForm):
    # El campo 'cliente' se define aquí, y su queryset se filtrará en el __init__
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(), # Se inicializa con todos, luego se filtra
        label="Cliente",
        empty_label="Selecciona un cliente" # Opción para no seleccionar ninguno inicialmente
    )

    class Meta:
        model = TodoItem
        fields = [
            'oportunidad', 'cliente', 'contacto', 'monto', 
            'probabilidad_cierre', 'mes_cierre', 'area', 'producto', 
            'comentarios'
        ]
        widgets = {
            'comentarios': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) # Obtener el usuario de los kwargs
        super().__init__(*args, **kwargs)

        # Si el usuario existe y no es supervisor, filtrar los clientes
        if user and not user.groups.filter(name='Supervisores').exists():
            self.fields['cliente'].queryset = Cliente.objects.filter(asignado_a=user)
        
        # Asegúrate de que el campo 'usuario' no se muestre en el formulario
        # Ya que se asigna automáticamente en la vista
        if 'usuario' in self.fields:
            del self.fields['usuario']

        # Añadir clases de Tailwind para estilizar los campos del formulario
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'})


class VentaFilterForm(forms.Form):
    # Campos de filtro
    area = forms.ChoiceField(choices=[('', 'Todas las Áreas')] + list(TodoItem.AREA_CHOICES), required=False, label="Área")
    producto = forms.ChoiceField(choices=[('', 'Todos los Productos')] + list(TodoItem.PRODUCTO_CHOICES), required=False, label="Producto")
    orden_monto = forms.ChoiceField(
        choices=[
            ('', 'Ordenar por'),
            ('monto_asc', 'Monto Ascendente'),
            ('monto_desc', 'Monto Descendente')
        ],
        required=False,
        label="Ordenar por Monto"
    )
    probabilidad_min = forms.IntegerField(required=False, min_value=0, max_value=100, label="Prob. Mínima (%)")
    probabilidad_max = forms.IntegerField(required=False, min_value=0, max_value=100, label="Prob. Máxima (%)")
    mes_cierre = forms.ChoiceField(choices=[('', 'Todos los Meses')] + list(TodoItem.MES_CHOICES), required=False, label="Mes de Cierre")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Añadir clases de Tailwind para estilizar los campos del formulario
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'})

