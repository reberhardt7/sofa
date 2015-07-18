class JackException(Exception):

	def __init__(self, message):
		super(JackException, self).__init__(message)

class ConfigurationException(JackException):

	def __init__(self, message):
		super(ConfigurationException, self).__init__(message)
