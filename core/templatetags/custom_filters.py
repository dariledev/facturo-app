# your_app/templatetags/custom_filters.py

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    """
    Multiplie la valeur par l'argument.
    Utilisation: {{ value|multiply:arg }}
    Gère les types Decimal pour les calculs monétaires.
    """
    try:
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError):
        try:
            return float(value) * float(arg)
        except (ValueError, TypeError):
            return '' # Retourne une chaîne vide en cas d'erreur de conversion

@register.filter
def divide(value, arg):
    """
    Divise la valeur par l'argument.
    Utilisation: {{ value|divide:arg }}
    Gère les types Decimal pour les calculs monétaires.
    """
    try:
        arg_decimal = Decimal(arg)
        if arg_decimal == 0:
            return 0 # Évite la division par zéro
        return Decimal(value) / arg_decimal
    except (ValueError, TypeError):
        try:
            arg_float = float(arg)
            if arg_float == 0:
                return 0
            return float(value) / arg_float
        except (ValueError, TypeError):
            return '' # Retourne une chaîne vide en cas d'erreur de conversion