"""
Contains common writer functions for converting information received via the
API into a format for database storage.
"""

def boolean_writer(value):
	if str(value).lower() in ['t', 'true', '1']:
		return True
	elif str(value).lower() in ['f', 'false', '0']:
		return False
	else:
		raise ValueError('%r is not a valid boolean' % value)

def date_writer(value):
	return datetime.strptime(value, '%Y-%m-%d')

def datetime_writer(value):
	return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
