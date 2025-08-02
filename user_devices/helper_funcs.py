from fractions import Fraction
from datetime import datetime, timedelta
import logging as logger

# Helper to sanitize variable names
def sanitize_variable_name(name):
    return name.replace("-", "_").replace(" ", "_")

# Helper to convert raw value to float
def convert_value(raw_value, conversion_factor):
    try:
        logger.info(f"Conv factor from mapping: {conversion_factor}")
        if conversion_factor.__contains__("/"):
            conversion_factor = float(Fraction(conversion_factor))
        else:
            conversion_factor = float(conversion_factor)
    except (ValueError, TypeError, ZeroDivisionError):
        logger.warning(f"Invalid conversion factor: {conversion_factor}. Defaulting to 0.")
        conversion_factor = 0.0
    logger.info(f"Conversion factor: {conversion_factor}")
    return raw_value * conversion_factor
