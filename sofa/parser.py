import yaml
import inspect

from structure import APIAttribute, APIValidator
from responses import ResourceException
from config import get_resource
from tools import eval_with_deps
from exceptions import (
    ConfigurationException,
    )

from sqlalchemy.orm.attributes import InstrumentedAttribute

from pprint import pformat

import logging
log = logging.getLogger(__name__)

def find_class(name):
    cls = get_resource(name)
    if not cls:
        raise ConfigurationException('Could not find APIResource class %r' % name)
    return cls

def get_handler_func(cls, string, dependencies={}):
    """
    Get a handler/callback function from string If cls contains a function whose
    name is in string, this will return that function. Otherwise, it will try to
    parse string as a lambda function.
    """
    string = string.strip()
    # TODO: Allow setting a handler func from the dependencies list (i.e. not
    # only lambdas and functions inside the target class)
    if hasattr(cls, string):
        return getattr(cls, string)
    elif 'lambda ' in string or 'lambda:' in string:
        try:
            # Eval the lambda to ensure proper syntax
            func = eval(string)
        except (NameError, SyntaxError, ImportError), e:
            raise ConfigurationException('Could not parse "%s" as a lambda function: %s, %s' % (string, type(e).__name__, e.message))
        for name, dep in dependencies.iteritems():
            # TODO: fix this
            # if name in func.__globals__:
            #     raise ConfigurationException('Import %r conflicts with global namespace' % name)
            func.__globals__[name] = dep
        return func
    else:
        # Try parsing the string as a symbol
        try:
            return eval_with_deps(string, dependencies)
        except (NameError, SyntaxError):
            raise ConfigurationException('Could not find function %s in %s' % (string, cls))

def parse_dependencies(dep_list):
    validators = __import__('sofa.validators')
    core_deps = {name: getattr(validators, name)
                 for name in dir(validators)
                 if name.endswith('Validator')}
    readers = __import__('sofa.readers')
    core_deps.update({name: getattr(readers, name)
                      for name in dir(readers)
                      if name.endswith('reader')})
    writers = __import__('sofa.writers')
    core_deps.update({name: getattr(writers, name)
                      for name in dir(writers)
                      if name.endswith('reader')})
    types = __import__('sofa.types')
    core_deps.update({name: getattr(types, name)
                      for name in dir(types)
                      if name[0] == name[0].upper()
                      and not name.endswith('Validator')
                      and not name.startswith('_')})

    dependencies = core_deps

    for dep in dep_list:
        if ':' in dep or isinstance(dep, dict):
            # We are doing a "from x import y"
            module = (dep.split(':',1)[0] if ':' in dep else dep.keys()[0]).strip()
            children_str = (dep.split(':',1)[1] if ':' in dep else dep.values()[0]).strip()
            children = [ c.strip() for c in children_str.split(',') ]
            tmp = __import__(module, fromlist=children)
            for child in children:
                if child in dependencies:
                    log.warning('Import {}:{} conflicts with existing import! The existing import will be overwritten.'.format(module, child))
                dependencies[child] = getattr(tmp, child)
        elif '.' in dep:
            # We are doing an "import x.y"
            module = dep.split('.',1)[0]
            if module in dependencies:
                log.warning('Import {} conflicts with an existing import! The existing import will be overwritten.'.format(dep))
            dependencies[module] = __import__(dep)
        else:
            # We are doing an "import x"
            if dep in dependencies:
                log.warning('Import {} conflicts with an existing import! The existing import will be overwritten.'.format(dep))
            dependencies[dep] = __import__(dep)

    return dependencies

def parse_attribute(name, attr_config, resource_class, dependencies, inherit_auth):
    # Get type info
    if 'type' in attr_config.keys():
        try:
            _type = get_handler_func(resource_class, attr_config['type'], dependencies=dependencies)
        except (NameError,ImportError,ConfigurationException), e:
            raise ConfigurationException('Could not find the type class for the %r attribute on %r! Original exception: %s' % (name, key, e))
        except Exception, e:
            raise ConfigurationException('Error parsing type for %s.%s (%s -> resources -> %s -> attrs -> %s -> type)! Original exception: %s' % (resource_class.__name__, name, path, key, name, e))
    else:
        _type = None
    # Get validator info
    if 'validator' in attr_config.keys():
        try:
            validator = get_handler_func(resource_class, attr_config['validator'], dependencies=dependencies)
        except (NameError,ImportError,ConfigurationException), e:
            raise ConfigurationException('Could not find the validator function for the %r attribute on %r! Original exception: %s' % (attr, key, e))
    else:
        validator = None
    # Get read/write info
    if not isinstance(attr_config.get('mutable', True), bool):
        raise ConfigurationException('mutable directive on %s:%s must be a boolean' \
                        % (key, name))
    mutable = attr_config.get('mutable', True)
    if not isinstance(attr_config.get('readable', True), bool):
        raise ConfigurationException('readable directive on %s:%s must be a boolean' \
                        % (key, name))
    readable = attr_config.get('readable', True)
    # Get reader/writer functions
    reader = get_handler_func(resource_class, attr_config.get('reader', 'None'), dependencies=dependencies)
    writer = get_handler_func(resource_class, attr_config.get('writer', 'None'), dependencies=dependencies)
    # Get auth, using context's as default
    attr_auth = get_handler_func(resource_class,
                                 attr_config['auth'], dependencies=dependencies) if 'auth' in attr_config \
                else inherit_auth
    # Get dynamic attribute info
    dynamic_params = []
    if 'dynamic' in attr_config.keys():
        if 'params' not in attr_config.keys():
            log.warning('{}.{} has been declared dynamic, but '
                'has no dynamic params'.format(info['class'], name))
        for param in attr_config.get('params', []):
            if isinstance(param, dict):
                param_name = param.keys()[0]
                if 'validator' in param.values()[0]:
                    try:
                        param_validator = get_handler_func(resource_class, param.values()[0]['validator'], dependencies=dependencies)
                    except (NameError,ImportError,ConfigurationException), e:
                        raise ConfigurationException('Could not handle the auth function for the %r dynamic parameter for attribute %r on %r! Original exception: %s' % (param_name, attr, key, e))
                else:
                    param_validator = None
                dynamic_params.append({'name': param_name,
                                       'validator': param_validator})
            else:
                dynamic_params.append({'name': param,
                                       'validator': None})
    if 'params' in attr_config.keys() and 'dynamic' not in attr_config.keys():
        raise ConfigurationException(
            'Params have been declared for the attribute {} in {} '
            'but the attribute is not dynamic!'.format(name, info['class']))
    leftover_keys = set(attr_config.keys()) - set(['name', 'validator', 'mutable',
                                                  'readable', 'reader',
                                                  'writer', 'auth', 'type',
                                                  'params', 'dynamic'])
    if leftover_keys:
        raise ConfigurationException('The directives %r are unrecognized in attrs context' \
                        % ', '.join(list(leftover_keys)))
    # Save info
    return APIAttribute(name, _type=_type,
                              validator=validator, readable=readable,
                              reader=reader, writable=mutable,
                              writer=writer, auth=attr_auth,
                              dynamic_params=dynamic_params,
                              cls=resource_class)


def parse_resources(resource_config, dependencies):
    resource_info = {}

    for key, info in resource_config.iteritems():
        # Find the resource class
        if 'class' not in info:
            raise ConfigurationException('Configuration must specify "class" directive for %r' % key)
        resource_class = find_class(info['class'])
        info.pop('class')

        root_accessible = info['root_accessible'] if 'root_accessible' in info else True

        # Set auth
        resource_auth = get_handler_func(resource_class, info['auth'], dependencies=dependencies) if 'auth' in info else None
        # For keeping track of the default auth in the current scope:
        auth = resource_auth
        info.pop('auth', None)

        # Get attribute info
        attrs = []
        for attr in info.get('attrs', []):
            if isinstance(attr, dict):
                attrs.append(parse_attribute(attr.keys()[0], attr.values()[0], resource_class, dependencies, resource_auth))
            else:
                attrs.append(APIAttribute(attr, cls=resource_class))
        info.pop('attrs', [])

        # Check for duplicate attributes
        attr_names = [ attr.key for attr in attrs ]
        if len(attr_names) != len(set(attr_names)):
            raise ConfigurationException('The configuration for %s lists duplicate attr keys.' % key)

        # Get default filters
        default_filters = info.get('default_filters', {})
        if not isinstance(default_filters, dict):
            raise ConfigurationException('The default_values for %r must be a dictionary (for each default filter, enter a line reading "attr_name: value")' % key)
        for filter_key, filter_value in default_filters.iteritems():
            # Make sure this is a filter for an attribute that exists
            if filter_key not in attr_names:
                raise ConfigurationException('Attribute %r (specified in %r > default_filters) is unknown' % (filter_key, key))
            # Make sure the specified value is an accepted value
            apiattr = next(attr for attr in attrs if attr.key == filter_key)
            try:
                apiattr.validate(filter_value)
            except ResourceException:
                raise ConfigurationException('The validator for attribute %r rejected the value %r (specified in %r > default_filters)' % (filter_key, filter_value, key))
            # If necessary, convert the value specified in the config into a
            # format that can be used in comparisons
            default_filters[filter_key] = apiattr._writer(filter_value)
        info.pop('default_filters', None)

        # Get child info
        children = {}
        if 'children' in info:
            for child in info['children']:
                if isinstance(child, dict):
                    # Config params were provided
                    name = child.keys()[0]
                    child = child[name]
                    references = find_class(child['references'])
                    secondary = find_class(child['secondary']) if 'secondary' in child else None
                    defaults = child.get('defaults', {})
                    default_pk = child.get('default_pk', None)
                    association_handler = get_handler_func(resource_class,
                                                           child['association_handler'], dependencies=dependencies) \
                                          if 'association_handler' in child else None
                    disassociation_handler = get_handler_func(resource_class,
                                                           child['disassociation_handler'], dependencies=dependencies) \
                                          if 'disassociation_handler' in child else None
                    delete_behavior = child.get('delete_behavior', 'delete')
                    child_auth = get_handler_func(resource_class, child['auth'], dependencies=dependencies) \
                                 if 'auth' in child else auth
                    leftover_keys = set(child.keys()) - set(['name', 'child', 'references',
                                                             'secondary', 'defaults',
                                                             'default_pk', 'association_handler',
                                                             'disassociation_handler',
                                                             'delete_behavior', 'auth'])
                    if leftover_keys:
                        raise ConfigurationException('The directives %s are unrecognized in children context'\
                                        % ', '.join(list(leftover_keys)))
                    children[name] = {'references': references,
                                      'secondary': secondary,
                                      'defaults': defaults,
                                      'default_pk': default_pk,
                                      'association_handler': association_handler,
                                      'disassociation_handler': disassociation_handler,
                                      'delete_behavior': delete_behavior,
                                      'auth': auth}
                else:
                    # Only the name was provided
                    children[child] = child
            info.pop('children')

        # Manage default actions
        if 'list' in info and not info['list']:
            info['list'] = {}
        list_ = {'method': 'GET',
                 'url': key,
                 'params': info['list'].get('params', []),
                 'auth': get_handler_func(resource_class, info['list']['auth'], dependencies=dependencies) \
                         if 'auth' in info['list'] else auth} \
                 if 'list' in info else None
        info.pop('list', None)

        if 'create' in info and not info['create']:
            info['create'] = {}
        create = {'method': 'POST',
                  'url': key,
                  'required_fields': info['create'].get('required_fields', []),
                  'optional_fields': info['create'].get('optional_fields', []),
                  'auth': get_handler_func(resource_class, info['create']['auth'], dependencies=dependencies) \
                          if 'auth' in info['create'] else auth} \
                  if 'create' in info else None
        info.pop('create', None)

        if create and set(create['required_fields']) - set(attr_names):
            raise ConfigurationException('The configuration for %s lists required_fields ' % key \
                          + 'that are not included in the attr list.')

        if create and set(create['optional_fields']) - set(attr_names):
            raise ConfigurationException('The configuration for %s lists optional_fields ' % key \
                          + 'that are not included in the attr list.')

        if 'read' in info and not info['read']:
            info['read'] = {}
        read = {'method': 'GET',
                'url': key+'/:'+resource_class.primary_key_name(),
                'auth': get_handler_func(resource_class, info['read']['auth'], dependencies=dependencies) \
                        if 'auth' in info['read'] else auth} \
                if 'read' in info else None
        info.pop('read', None)

        if 'update' in info and not info['update']:
            info['update'] = {}
        update = {'method': 'PATCH',
                  'url': key+'/:'+resource_class.primary_key_name(),
                  'auth': get_handler_func(resource_class, info['update']['auth'], dependencies=dependencies) \
                          if 'auth' in info['update'] else auth} \
                  if 'update' in info else None
        info.pop('update', None)

        if 'delete' in info and not info['delete']:
            info['delete'] = {}
        delete = {'method': 'DELETE',
                  'url': key+'/:'+resource_class.primary_key_name(),
                  'auth': get_handler_func(resource_class, info['delete']['auth'], dependencies=dependencies) \
                          if 'auth' in info['delete'] else auth} \
                  if 'delete' in info else None
        info.pop('delete', None)

        # Get other actions
        other_actions = {}
        for action, directives in info.iteritems():
            other_actions[action] = {'method': directives['method'],
                                     'url': directives['url'],
                                     'params': directives.get('params', None)}
        # ^ TEMPORARY HALF-IMPLEMENTATION

        # Add resource info
        resource_info[resource_class.__name__] = {'group_name': key,
                                                  'root_accessible': root_accessible,
                                                  'attrs': attrs,
                                                  'default_filters': default_filters,
                                                  'children': children,
                                                  'auth': resource_auth,
                                                  'list': list_,
                                                  'create': create,
                                                  'read': read,
                                                  'update': update,
                                                  'delete': delete}
        resource_info[resource_class.__name__].update(other_actions)
    return resource_info


def get_resource_info(path):
    with open(path, 'r') as f:
        data = yaml.load(f)

    try:
        resource_module_names = data['resource_modules']
    except KeyError:
        raise ConfigurationException('Configuration must specify "resource_modules" directive.')

    resource_modules = []
    for mod in resource_module_names:
        # We import the module containing resource classes so that the
        # resource classes are loaded and registered in the SQLAlchemy
        # registry. We don't actually need the module itself at all.
        # Still, we'll store a reference to the module as part of the
        # API config in case something later in program execution needs
        # it
        resource_modules.append(__import__(mod))

    dependencies = parse_dependencies(data.get('dependencies', []))

    try:
        resources_data = data['resources']
    except KeyError:
        raise ConfigurationException('Configuration must specify "resources" directive.')

    resource_info = parse_resources(resources_data, dependencies)

    log.info('Loaded resources %s', ', '.join([cls for cls, info in resource_info.iteritems()]))
    log.debug(pformat(resource_info))
    return {'resource_modules': resource_modules,
            'dependencies': dependencies,
            'api': resource_info}
