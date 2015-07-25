class SofaException(Exception):

	def __init__(self, message):
		super(SofaException, self).__init__(message)

class ConfigurationException(SofaException):

	def __init__(self, message):
		super(ConfigurationException, self).__init__(message)
