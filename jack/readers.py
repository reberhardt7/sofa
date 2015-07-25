"""
Contains common reader functions for converting database information into a
format returnable by the API
"""

from datetime import datetime

from structure import APIReader

class DateReader(APIReader):

    def read(self, value):
        return datetime.strftime(value, '%Y-%m-%d') if value else value


class DatetimeReader(APIReader):
    
    def read(self, value):
        return datetime.strftime(value, "%Y-%m-%dT%H:%M:%SZ") if value else value
