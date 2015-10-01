import structure

from sqlalchemy.orm import _mapper_registry

from exceptions import ConfigurationException

import logging
log = logging.getLogger(__name__)

_api_config = {}
_root_collections = []
_collection_class_map = {}
_dbsession = None
_session_lookup_func = None
_session_duration = 86400   # one day

# _api_config, _root_collections, _collection_class_map, and _dbsession are
# private and wrapped in getter functions because __init__ might import a module
# that imports one of those before load_api_config has been called; then, if the
# module tries to use it, it'll just be using an empty dict, since the import
# hasn't been updated. This is a better way to make sure nobody tries reading
# api_config until __init__ has finished and load_api_config has been called

def load_api_config(api_config_path):
    global _api_config
    from parser import get_resource_info
    _api_config = get_resource_info(api_config_path)
    for k, v in _api_config['api'].iteritems():
        _collection_class_map[v['group_name']] = k
        if v['root_accessible']:
            _root_collections.append(v['group_name'])

def set_sqla_session(session):
    global _dbsession
    _dbsession = session

def sqla_session():
    if not _dbsession:
        log.warning('A SQLAlchemy session factory has not been configured. '
                    'Please call sofa.configure() and pass the sqla_session '
                    'argument')
    return _dbsession

def set_session_lookup_func(func):
    global _session_lookup_func
    _session_lookup_func = func

def session_lookup_func():
    return _session_lookup_func

def set_session_duration(time):
    global _session_duration
    _session_duration = time

def session_duration():
    return _session_duration

def root_collections():
    if not _root_collections:
        log.warning('No root collections were found. Either you have not '
            'called sofa.configure() with api_config_path or you have no '
            'root-accessible resources defined.')
    return _root_collections

def resource_modules():
    return _api_config.get('resource_modules', [])

def dependencies():
    return _api_config.get('dependencies', {})

def api_config():
    return _api_config.get('api', {})

def collection_class_map():
    return _collection_class_map

def get_class_name(collection_name):
    """
    Convenience function to look up the APIResource class associated with a
    collection
    """
    return _collection_class_map[collection_name]

def resource_registry():
    sqla_classes = [ mapper_weakref().class_
                     for mapper_weakref, state in _mapper_registry.data.iteritems()
                     if state is True ]
    virtual_classes = structure.VirtualResourceRegistry.resources
    return sqla_classes + virtual_classes

def resource_class_names():
    return [x.__name__ for x in resource_registry()]

def get_resource(resource_name):
    log.debug('Resolving {} in resource registry'.format(resource_name))
    resource = next((x for x in resource_registry() if x.__name__ == resource_name), None)
    log.debug('Resolved resource: {}'.format(resource))
    return resource

def getapiattr(cls, name):
    """
    Like getattr, but returns an APIAttribute instead of the actual attribute
    on the class
    """
    if isinstance(cls, basestring):
        cls = get_resource(cls)
    return next(attr for attr in api_config()[cls.__name__]['attrs'] if attr.key == name)
