# accounts/templatetags/role_tags.py
from django import template

register = template.Library()

@register.filter
def has_group(user, group_name: str) -> bool:
    """True si el usuario es superuser o pertenece al grupo dado."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=group_name).exists()
