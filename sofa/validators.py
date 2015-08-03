"""
Contains common validator classes for verifying data integrity
in the API
"""

import re

from datetime import datetime

from structure import APIValidator

from responses import ResourceException

from validate_email import validate_email


class NumericIdValidator(APIValidator):
    """
    Validates integer-based resource IDs
    """

    def __init__(self, attr_name=None):
        self.attr_name = attr_name

    def validate(self, value):
        if not str(value).isdigit():
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field is not a valid positive integer." % self.attr_name)


class StringIdValidator(APIValidator):
    """
    Validates string-based resource IDs
    """

    def __init__(self, attr_name=None, id_length=6):
        self.attr_name = attr_name
        self.id_length = id_length

    def validate(self, value):
        if len(value.strip()) != self.id_length:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be %s characters long." % (self.attr_name, self.id_length))
        if not re.match('^[\w-]+$', value.strip()):
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field may only contain alphanumeric characters." % self.attr_name)


class BooleanValidator(APIValidator):
    """
    Validates booleans
    """

    def __init__(self, attr_name=None):
        self.attr_name = attr_name

    def validate(self, value):
        if str(value).lower() not in ('true', 't', '1', 'false', 'f', '0'):
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field is invalid (%r is not a valid boolean value)." % (self.attr_name, value))


class IntegerValidator(APIValidator):
    """
    Validates integers
    """

    def __init__(self, attr_name=None, min=None, max=None, allow_negative=True):
        self.attr_name = attr_name
        self.min = min
        self.max = max
        self.allow_negative = allow_negative

    def validate(self, value):
        try:
            if self.min and not int(value) >= self.min:
                raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be at least %s." % (self.attr_name, self.min))
            if self.max and not int(value) <= self.max:
                raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be less than %s." % (self.attr_name, self.max))
            if not self.allow_negative and int(value) < 0:
                raise ResourceException(400, 'bad_'+self.attr_name, "The %s field cannot be less than zero." % self.attr_name)
        except ValueError:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be an integer." % self.attr_name)


class FloatValidator(APIValidator):
    """
    Validates decimal numbers
    """

    def __init__(self, attr_name=None, min=None, max=None):
        self.attr_name = attr_name
        self.min = min
        self.max = max

    def validate(self, value):
        try:
            if self.min and not float(value) >= self.min:
                raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be at least %s." % (self.attr_name, self.min))
            if self.max and not float(value) <= self.max:
                raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be less than %s." % (self.attr_name, self.max))
        except ValueError:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be a decimal number." % self.attr_name)


class StringValidator(APIValidator):
    """
    Validates strings of text, with certain constraints
    """

    def __init__(self, attr_name=None, min_len=None, max_len=None, allow_digits=True, allow_special_chars=True, valid_values=None):
        self.attr_name = attr_name
        self.min_len = min_len
        self.max_len = max_len
        self.allow_digits = allow_digits
        self.allow_special_chars = allow_special_chars
        self.valid_values = valid_values

    def validate(self, value):
        value = str(value).strip()
        if self.min_len and len(value) < self.min_len:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field must be at least %s characters long." % (self.attr_name, self.min_len))
        if self.max_len and len(value) > self.max_len:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field cannot exceed %s characters." % (self.attr_name, self.max_len))
        if not self.allow_digits and re.compile('\d').search(value):
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field cannot contain digits." % self.attr_name)
        if not self.allow_special_chars and not re.match('^[\w-]+$', value):
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field cannot contain special characters." % self.attr_name)
        if self.valid_values and value not in self.valid_values:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field is invalid; %r is not a valid value. Accepted values: %s" \
                                                                % (self.attr_name, value, ', '.join([ '%r' % val for val in self.valid_values ])))


class DateValidator(APIValidator):
    """
    Validates dates in YYYY-mm-dd form (%Y-%m-%d strftime form)
    """
    
    def __init__(self, attr_name=None):
        self.attr_name = attr_name

    def validate(self, value):
        if not value:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field is mandatory." % self.attr_name)
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ResourceException(400, 'bad_'+self.attr_name, 'The date %s is invalid for the %s field. Dates must be in YYYY-mm-dd form.' % (value, self.attr_name))


class DatetimeValidator(APIValidator):
    """
    Validates datetimes in YYYY-mm-ddTHH:MM:SSZ form (%Y-%m-%dT%H:%M:%SZ strftime form)
    """
    
    def __init__(self, attr_name=None):
        self.attr_name = attr_name

    def validate(self, value):
        if not value:
            raise ResourceException(400, 'bad_'+self.attr_name, "The %s field is mandatory." % self.attr_name)
        try:
            datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            raise ResourceException(400, 'bad_'+self.attr_name, 'The date %s is invalid for the %s field. Dates must be in YYYY-mm-ddTHH:MM:SSZ (%%Y-%%m-%%dT%%H:%%M:%%SZ) form.' % (value, self.attr_name))


class EmailValidator(StringValidator):
    """
    Validates email addresses
    """

    def __init__(self):
        super(EmailValidator, self).__init__(min_len=5, max_len=255)

    def validate(self, value):
        super(EmailValidator, self).validate(value)
        if not validate_email(value):
            raise ResourceException(400, 'bad_'+self.attr_name, "The email address is not valid.")


class ZipCodeValidator(StringValidator):
    """
    Validates 5-digit US zip codes
    """

    def __init__(self):
        super(ZipCodeValidator, self).__init__(min_len=5, max_len=5)

    def validate(self, value):
        if not re.match(r'^\d{5}$', value):
            raise ResourceException(400, 'bad_'+self.attr_name, 'The zip code "%s" is not valid.' % value)

