"""
Contains common reader functions for converting database information into a
format returnable by the API
"""

from datetime import datetime

def date_reader(value):
    return datetime.strftime(value, '%Y-%m-%d') if value else value

def datetime_reader(value):
    return datetime.strftime(value, "%Y-%m-%dT%H:%M:%SZ") if value else value
