from structure import SofaType
from readers import date_reader, datetime_reader
from writers import boolean_writer, date_writer, datetime_writer
from validators import (
	NumericIdValidator,
	StringIdValidator,
	BooleanValidator,
	IntegerValidator,
	FloatValidator,
	StringValidator,
	DateValidator,
	DatetimeValidator,
	EmailValidator,
	ZipCodeValidator,
	)


class NumericId(SofaType):
	"""
	Represents integer-based resource IDs
	"""

	def __init__(self):
		self.validator = NumericIdValidator()

	def __repr__(self):
		return "<NumericId()>"


class StringId(SofaType):
	"""
	Represents string-based resource IDs
	"""

	def __init__(self, id_length):
		self.id_length = id_length
		self.validator = StringIdValidator(id_length=id_length)

	def __repr__(self):
		return "<StringId(id_length=%r)>" % self.id_length


class Boolean(SofaType):

	def __init__(self, nullable=False):
		self.nullable = nullable
		self.validator = BooleanValidator(nullable=nullable)
		self.writer = boolean_writer

	def __repr__(self):
		return "<Boolean()>"


class Integer(SofaType):

	def __init__(self, min=None, max=None, unique=False, nullable=False):
		self.min = min
		self.max = max
		self.unique = unique
		self.nullable = nullable
		self.validator = IntegerValidator(min=min, max=max, unique=unique, nullable=nullable)
		self.writer = lambda value: int(value)

	def __repr__(self):
		return "<Integer(min=%r, max=%r)>" % (self.min, self.max)


class Float(SofaType):

	def __init__(self, min=None, max=None, unique=False, nullable=False):
		self.min = min
		self.max = max
		self.unique = unique
		self.nullable = nullable
		self.validator = FloatValidator(min=min, max=max, unique=unique, nullable=nullable)
		self.writer = lambda value: float(value)

	def __repr__(self):
		return "<Float(min=%r, max=%r)>" % (self.min, self.max)


class String(SofaType):

	def __init__(self, min_len=None, max_len=None, allow_digits=True, allow_special_chars=True, valid_values=None, unique=False, nullable=False):
		self.min_len = min_len
		self.max_len = max_len
		self.allow_digits = allow_digits
		self.allow_special_chars = allow_special_chars
		self.valid_values = valid_values
		self.unique = unique
		self.nullable = nullable
		self.validator = StringValidator(min_len=min_len, max_len=max_len,
										 allow_digits=allow_digits,
										 allow_special_chars=allow_special_chars,
										 valid_values=valid_values,
										 unique=unique,
										 nullable=nullable)

	def __repr__(self):
		return "<String()>"


class Date(SofaType):

	def __init__(self, require_future=False, require_past=False, nullable=False):
		self.require_future = require_future
		self.require_past = require_past
		self.nullable = nullable
		self.validator = DateValidator(require_future=require_future, require_past=require_past, nullable=nullable)
		self.reader = date_reader
		self.writer = date_writer

	def __repr__(self):
		return "<Date(require_future=%r, require_past=%r)>" % (self.require_future, self.require_past)


class Datetime(SofaType):

	def __init__(self, require_future=False, require_past=False, nullable=False):
		self.require_future = require_future
		self.require_past = require_past
		self.validator = DatetimeValidator(require_future=require_future, require_past=require_past, nullable=nullable)
		self.reader = datetime_reader
		self.writer = datetime_writer

	def __repr__(self):
		return "<Datetime(require_future=%r, require_past=%r)>" % (self.require_future, self.require_past)


class Email(SofaType):

	def __init__(self, unique=False, nullable=False):
		self.unique = unique
		self.nullable = nullable
		self.validator = EmailValidator(unique=unique, nullable=nullable)

	def __repr__(self):
		return "<Email()>"


class ZipCode(SofaType):

	def __init__(self, unique=False, nullable=False):
		self.unique = unique
		self.nullable = nullable
		self.validator = ZipCodeValidator(unique=unique, nullable=nullable)

	def __repr__(self):
		return "<ZipCode()>"
