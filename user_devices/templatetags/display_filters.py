from django import template

register = template.Library()

@register.filter
def display_varname(name):
    name = name.replace("_", " ")
    name = name.replace("L1 N", "L1-N")
    name = name.replace("L2 N", "L2-N")
    name = name.replace("L3 N", "L3-N")
    return name