# Renamed to avoid potential conflicts with user imports
import re as _re
from config import resource_class_names as _resource_class_names
from config import get_resource as _get_resource
from config import dependencies as _dependencies
import logging as _logging
import inspect as _inspect
_log = _logging.getLogger(__name__)

# Hack to get around circularly importing validators
# -> structure -> tools -> validators
_loaded_core_deps = {}
def _core_deps():
	global _loaded_core_deps
	if _loaded_core_deps:
		return _loaded_core_deps
	else:
		validators = __import__('sofa.validators')
		_loaded_core_deps = {name: getattr(validators, name)
							 for name in dir(validators)
							 if name.endswith('Validator')}
		readers = __import__('sofa.readers')
		_loaded_core_deps.update({name: getattr(readers, name)
							 	  for name in dir(readers)
							 	  if name.endswith('Reader')})
		return _loaded_core_deps

def eval_with_deps(target, dependencies=None):
	"""
	Can eval a string using dependencies listed in the API config
	"""
	if not dependencies:
		dependencies = _dependencies()
	if isinstance(target, basestring):
		# Loop until we complete successfully (i.e. dependencies successfully
		# resolved) or we raise an exception
		last_dependency_error = None
		while True:
			try:
				return eval(target)
			except NameError, e:
				# Let's try resolving the dependency
				if _re.findall("name '(\w+)' is not defined",str(e)):
					dep = _re.findall("name '(\w+)' is not defined",str(e))[0]
					if dep == last_dependency_error:
						# We're in a loop. The NameError must be coming from
						# somewhere else deeper in the code
						raise
					last_dependency_error = dep
					if dep in globals():
						# We can't import this name or it will conflict with an
						# existing name and potentially mess up this function.
						raise ImportError('Import {} conflicts with an existing name in the global namespace'.format(dep))
					if dep in _resource_class_names():
						# This is the name of a resource class. Let's try
						# importing it
						_log.debug('Importing %r from resource class list', dep)
						globals()[dep] = _get_resource(dep)
					elif dep in _core_deps():
						_log.debug('Importing %r from validators', dep)
						globals()[dep] = _core_deps()[dep]
					elif dep in dependencies.keys():
						_log.debug('Importing %r from dependency list', dep)
						globals()[dep] = dependencies[dep]
					else:
						# We don't know what this is.
						raise
				else:
					raise
	else:
		return target

def exec_function(func, *args, **kwargs):
	"""
	Handles the execution of a function which may or may not be a lambda
	with additional dependencies (i.e. the lambda may reference resource
	classes or other dependencies specified in the API config file). If
	this is the case, this function will attempt to resolve those dependencies.
	"""
	if isinstance(func, basestring):
		# This is a lambda function
		return eval_with_deps(func)(*args, **kwargs)
	else:
		# This is a function in some actual code somewhere. If dependencies
		# don't resolve, that's not our problem anymore.
		return func(*args, **kwargs)

def func_params(func):
	if isinstance(func, basestring):
		return _inspect.getargspec(eval(func))[0]
	else:
		return _inspect.getargspec(func)[0]
