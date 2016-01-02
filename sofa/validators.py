"""
Contains common validator classes for verifying data integrity
in the API
"""

import re

from datetime import datetime

from structure import APIValidator
from responses import ResourceException
from config import sqla_session

from validate_email import validate_email

def build_unique_query(cls, key, value):
    return sqla_session().query(cls).filter(getattr(cls, key)==value)


class NumericIdValidator(APIValidator):
    """
    Validates unique integer-based resource IDs
    """
    def validate(self, value, attr):
        if not str(value).isdigit():
            raise ResourceException(400, 'bad_'+attr.key, "The %s field is not a valid positive integer." % attr.key)
        if build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)


class StringIdValidator(APIValidator):
    """
    Validates unique string-based resource IDs
    """

    def __init__(self, id_length=6):
        self.id_length = id_length

    def validate(self, value, attr):
        if value is None:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be null." % attr.key)
        value = str(value).strip()
        if len(value.strip()) != self.id_length:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field must be %s characters long." % (attr.key, self.id_length))
        if not re.match('^[\w-]+$', value.strip()):
            raise ResourceException(400, 'bad_'+attr.key, "The %s field may only contain alphanumeric characters." % attr.key)
        if build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)


class BooleanValidator(APIValidator):
    """
    Validates booleans
    """

    def __init__(self, nullable=False):
        self.nullable = nullable

    def validate(self, value, attr):
        valid_values = ['true', '1', 'false', '0']
        if self.nullable:
            valid_values.append(None)
        if str(value).lower() not in valid_values:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field is invalid (%r is not a valid boolean value)." % (attr.key, value))


class IntegerValidator(APIValidator):
    """
    Validates integers
    """

    def __init__(self, min=None, max=None, allow_negative=True, unique=False, nullable=False):
        self.min = min
        self.max = max
        self.allow_negative = allow_negative
        self.unique = unique
        self.nullable = nullable

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        try:
            value = int(value)
            if self.min is not None and not int(value) >= self.min:
                raise ResourceException(400, 'bad_'+attr.key, "The %s field must be at least %s." % (attr.key, self.min))
            if self.max is not None and not int(value) <= self.max:
                raise ResourceException(400, 'bad_'+attr.key, "The %s field must be less than %s." % (attr.key, self.max))
            if not self.allow_negative and int(value) < 0:
                raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be less than zero." % attr.key)
        except (ValueError, TypeError):
            raise ResourceException(400, 'bad_'+attr.key, "The %s field must be an integer." % attr.key)
        if self.unique and build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)


class FloatValidator(APIValidator):
    """
    Validates decimal numbers
    """

    def __init__(self, min=None, max=None, unique=False, nullable=False):
        self.min = float(min) if min is not None else None
        self.max = float(max) if max is not None else None
        self.unique = unique
        self.nullable = nullable

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        try:
            value = float(value)
            if self.min is not None and float(value) < self.min:
                raise ResourceException(400, 'bad_'+attr.key, "The %s field must be at least %s." % (attr.key, self.min))
            if self.max is not None and float(value) > self.max:
                raise ResourceException(400, 'bad_'+attr.key, "The %s field must be less than %s." % (attr.key, self.max))
        except (ValueError, TypeError):
            raise ResourceException(400, 'bad_'+attr.key, "The %s field must be a decimal number." % attr.key)
        if self.unique and build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)


class StringValidator(APIValidator):
    """
    Validates strings of text, with certain constraints
    """

    def __init__(self, min_len=None, max_len=None, allow_digits=True, allow_special_chars=True, valid_values=None, unique=False, nullable=False):
        self.min_len = min_len
        self.max_len = max_len
        self.allow_digits = allow_digits
        self.allow_special_chars = allow_special_chars
        self.valid_values = valid_values
        self.unique = unique
        self.nullable = nullable

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        elif value is None:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be null." % attr.key)

        value = str(value).strip()
        if self.min_len and len(value) < self.min_len:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field must be at least %s characters long." % (attr.key, self.min_len))
        if self.max_len and len(value) > self.max_len:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot exceed %s characters." % (attr.key, self.max_len))
        if not self.allow_digits and re.compile('\d').search(value):
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot contain digits." % attr.key)
        if not self.allow_special_chars and not re.match('^[\w-]+$', value):
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot contain special characters." % attr.key)
        if self.valid_values and value not in self.valid_values:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field is invalid; %r is not a valid value. Accepted values: %s" \
                                                                % (attr.key, value, ', '.join([ '%r' % val for val in self.valid_values ])))
        if self.unique and build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)


class DateValidator(APIValidator):
    """
    Validates dates in YYYY-mm-dd form (%Y-%m-%d strftime form)
    """
    
    def __init__(self, require_future=False, require_past=False, nullable=False):
        self.require_future = require_future
        self.require_past = require_past
        self.nullable = nullable

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        elif value is None:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be null." % attr.key)

        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ResourceException(400, 'bad_'+attr.key, 'The date %r is invalid for the %s field. Dates must be in YYYY-mm-dd form.' % (value, attr.key))
        if self.require_future and datetime.strptime(value, '%Y-%m-%d') < datetime.utcnow():
            raise ResourceException(400, 'bad_'+attr.key, 'The %s field must be a future date, but a past date was submitted.' % attr.key)
        if self.require_past and datetime.strptime(value, '%Y-%m-%d') > datetime.utcnow():
            raise ResourceException(400, 'bad_'+attr.key, 'The %s field must be a past date, but a future date was submitted.' % attr.key)


class DatetimeValidator(APIValidator):
    """
    Validates datetimes in YYYY-mm-ddTHH:MM:SSZ form (%Y-%m-%dT%H:%M:%SZ strftime form)
    """
    
    def __init__(self, require_future=False, require_past=False, nullable=False):
        self.require_future = require_future
        self.require_past = require_past
        self.nullable = nullable

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        elif value is None:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be null." % attr.key)

        try:
            datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            raise ResourceException(400, 'bad_'+attr.key, 'The date %s is invalid for the %s field. Dates must be in YYYY-mm-ddTHH:MM:SSZ (%%Y-%%m-%%dT%%H:%%M:%%SZ) form.' % (value, attr.key))
        if self.require_future and datetime.strptime(value, '%Y-%m-%d') < datetime.utcnow():
            raise ResourceException(400, 'bad_'+attr.key, 'The %s field must be a future date, but a past date was submitted.' % attr.key)
        if self.require_past and datetime.strptime(value, '%Y-%m-%d') > datetime.utcnow():
            raise ResourceException(400, 'bad_'+attr.key, 'The %s field must be a past date, but a future date was submitted.' % attr.key)


class EmailValidator(StringValidator):
    """
    Validates email addresses
    """

    def __init__(self, unique=False, nullable=False):
        self.unique = unique
        self.nullable = nullable
        super(EmailValidator, self).__init__(min_len=5, max_len=255)

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        elif value is None:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be null." % attr.key)

        super(EmailValidator, self).validate(value, attr)
        if not validate_email(value):
            raise ResourceException(400, 'bad_'+attr.key, "The email address is not valid.")
        if self.unique and build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)


class ZipCodeValidator(StringValidator):
    """
    Validates 5-digit US zip codes
    """

    def __init__(self, unique=False, nullable=False):
        self.unique = unique
        nullable = nullable
        super(ZipCodeValidator, self).__init__(min_len=5, max_len=5)

    def validate(self, value, attr):
        if self.nullable and value is None:
            return
        elif value is None:
            raise ResourceException(400, 'bad_'+attr.key, "The %s field cannot be null." % attr.key)

        if not re.match(r'^\d{5}$', value):
            raise ResourceException(400, 'bad_'+attr.key, 'The zip code "%s" is not valid.' % value)
        if self.unique and build_unique_query(attr.cls, attr.key, value).first():
            raise ResourceException(400, 'duplicate_'+attr.key, "The %s field is not unique." % attr.key)
