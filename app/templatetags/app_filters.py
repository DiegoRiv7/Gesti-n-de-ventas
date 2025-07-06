# cartera_clientes/app/templatetags/app_filters.py

from django import template
from decimal import Decimal, InvalidOperation
import locale

register = template.Library()

@register.filter
def format_currency_es(value):
    """
    Formatea un valor numérico como moneda en formato español (España).
    Utiliza el punto como separador de miles y la coma como separador decimal.
    Ejemplo: 1234.56 -> 1.234,56
    """
    if value is None:
        return "0,00" # Retorna un valor predeterminado si el valor es None

    try:
        # Intenta convertir el valor a Decimal para una precisión adecuada
        decimal_value = Decimal(value)
    except InvalidOperation:
        # Si no es un número válido, retorna el valor original o un mensaje de error
        return value # O puedes devolver "Formato inválido"

    # Intenta configurar el locale a español (España)
    # Primero 'es_ES.UTF-8' es el más común en sistemas Unix/Linux
    # Luego 'es_ES' como fallback para otros sistemas (ej. algunos Windows)
    # Finalmente, si ninguno funciona, se usa un formato manual
    try:
        locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'es_ES')
        except locale.Error:
            # Fallback manual si no se puede establecer el locale
            # Esto asegura que siempre se formatee correctamente
            formatted_value = f"{decimal_value:,.2f}"
            # Reemplaza la coma (separador de miles en inglés) por 'X' temporalmente
            # Reemplaza el punto (separador decimal en inglés) por coma
            # Reemplaza 'X' por punto
            return formatted_value.replace(",", "X").replace(".", ",").replace("X", ".")

    # Formatea el número a dos decimales con agrupamiento (separadores de miles)
    # y usa el formato de locale. El '%n' es para formato monetario, pero aquí
    # usamos '%.2f' para solo el número y luego ajustamos los separadores.
    formatted_value = locale.format_string("%.2f", decimal_value, grouping=True)

    # El locale.format_string ya debería haber aplicado los separadores correctos
    # (punto para miles, coma para decimales) si el locale se estableció bien.
    # No necesitamos más reemplazos si el locale funciona.

    return formatted_value

@register.filter
def div(value, arg):
    """
    Realiza una división de dos números.
    """
    try:
        # Convierte ambos valores a float para la operación de división
        numerator = float(value)
        denominator = float(arg)
        if denominator == 0:
            return value # Evita la división por cero, retorna el valor original
        return numerator / denominator
    except (ValueError, TypeError):
        # Captura errores si los valores no son numéricos
        return value # Retorna el valor original si hay un error

@register.filter
def mul(value, arg):
    """
    Realiza una multiplicación de dos números.
    """
    try:
        # Convierte ambos valores a float para la operación de multiplicación
        return float(value) * float(arg)
    except (ValueError, TypeError):
        # Captura errores si los valores no son numéricos
        return value # Retorna el valor original si hay un error

