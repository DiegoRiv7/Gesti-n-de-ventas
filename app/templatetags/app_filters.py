# cartera_clientes/app/templatetags/app_filters.py

from django import template
from decimal import Decimal, InvalidOperation
import locale

register = template.Library()

@register.filter
def format_currency_es(value):
    """
    Formatea un valor numérico como moneda en formato mexicano (MXN).
    Ejemplo: 1234.56 -> 1,234.56
    """
    if value is None:
        return "0.00" # Retorna un valor predeterminado si el valor es None

    try:
        # Intenta convertir el valor a Decimal para una precisión adecuada
        decimal_value = Decimal(value)
    except InvalidOperation:
        # Si no es un número válido, retorna el valor original o un mensaje de error
        return value # O puedes devolver "Formato inválido"

    # Formato manual: separador de miles = ',', decimal = '.'
    formatted_value = f"{decimal_value:,.2f}"
    
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

