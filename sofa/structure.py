import os
import requests
import collections
import transaction

from pprint import pformat

from inspect import isclass

from datetime import datetime, timedelta

from pyramid.httpexceptions import HTTPNotModified
from pyramid.threadlocal import get_current_request

from sqlalchemy import Column, Boolean, DateTime
from sqlalchemy.sql.expression import func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import orm

from responses import ResourceUpdated, ResourceException

from config import (
    sqla_session,
    session_lookup_func,
    api_config,
    resource_registry,
    session_duration,
    getapiattr,
    get_resource,
    )
from tools import exec_function, func_params

import logging
log = logging.getLogger(__name__)


class APIAttribute(object):
    def __init__(self, key, validator=None, readable=True, reader=None,
                 writable=True, writer=None, auth=None, cls=None, dynamic_params=[]):
        """
        Initializes an APIAttribute object, representing an attribute of an object in an API.
        Takes a `key` param, the name of the attribute to be displayed in the API and the name
        of the class variable that stores the data (e.g. if you want to have a `value` attribute
        of a resource, the resource class must have a `value` class attribute like a SQLAlchemy
        Column to store the data); a `validator` param, a reference to an APIValidator object or
        subclass (see framework.validators); a `readable` param, indicating whether or not the
        attribute should be displayed in API GET requests; a `reader` param, a reference to a
        function that interprets values from the database to be returned in the API (see
        `_reader()` docstring); a `writable` param, indicating whether or not the attribute
        should be mutable in API PATCH requests; and a `writer` param, a reference to a function
        that translates values from API requests to database values (see `._writer()` docstring).

        Note that `readable` and `writable` do NOT affect the APIAttribute's
        readability/writability within the read() and write() methods -- they only affect what's
        served over the HTTP REST API (i.e. they are implemented inside the APIResource class).
        """
        self.key = key
        if not validator:
            # If no valiator has been specified, use a dummy APIValidator that does nothing
            validator = APIValidator()
        if isinstance(validator, basestring):
            # We got a string as a validator (from a lambda function).
            # Need to wrap it in an APIValidator
            validator = APIValidator(validator)
        if isclass(validator):
            # Instantiate the validator if it is just a class reference
            # This allows us to do things like APIAttribute(validator=NumericIdValidator)
            # without unnecessary parentheses
            validator = validator()
        self.validator = validator
        if not hasattr(self.validator, 'attr_name') or not self.validator.attr_name:
            self.validator.attr_name = key
        self.readable = readable
        if reader and isclass(reader):
            reader = reader().read
        if reader:
            self._reader = reader
        self.writable = writable
        if writer:
            self._writer = writer
        self.auth = auth
        self.cls = cls
        self.dynamic_params = dynamic_params
        for param in self.dynamic_params:
            if param['validator'] and isclass(param['validator']):
                param['validator'] = param['validator']()
            elif not param['validator']:
                param['validator'] = APIValidator()
            param['validator'].attr_name = param['name']

    def __repr__(self):
        return "<APIAttribute(key=%r, validator=%r)>" % (self.key, self.validator)

    def get_class_attr(self, request):
        """
        Gets the actual attribute on the resource class. Calling
        cls.get_class_attr() is preferred to calling getattr(cls, attr.key) in
        the case of dynamic attributes, where a value needs to be passed before
        the attribute can be used in filters or order_by or what not. This
        function simplifies all that
        """
        if self.dynamic_params:
            # This is a dynamic attribute, and we need to pass the "attribute"
            # the appropriate parameters in order to get a "static attribute"
            # that can be used in sqla queries
            return getattr(self.cls, self.key)(**{p['name']: request.GET[p['name']] for p in self.dynamic_params})
        else:
            return getattr(self.cls, self.key)

    def read(self, instance):
        """
        Reads the attribute's value from the specified resource instance using the _reader()
        function.
        """
        if self.dynamic_params:
            # This is a dynamic attribute, and we need to pass the "attribute"
            # the appropriate parameters in order to get a value
            return self._reader(getattr(instance, self.key)(**{p['name']: instance.__request__.GET.get(p['name'], None) for p in self.dynamic_params}))
        else:
            return self._reader(getattr(instance, self.key))

    @staticmethod
    def _reader(value):
        """
        Default reader function to interpret a value from the database.
        Passed a value from the database in the param `value`, and must return a value to be
        used in the application. Use cases include formatting dates/times read from a database.
        """
        return value

    def reader(self, func):
        """ Decorator to override the attribute's reader (interpreter) function """
        self._reader = func
        return self

    def write(self, instance, value):
        """
        Writes a value to the specified resource instance using the _writer() function.
        Also validates the new value before writing using the APIAttribute's validator
        (APIValidator) object.
        """
        # Validate the value we'll be using
        self.validator.validate(value)
        # OK, we're ready to do the update... Get the class of the object we're updating
        resource_class = instance.__class__
        # Get the target class variable that we want to update (probably Column object)
        target = resource_class.__getattribute__(resource_class, self.key)
        # If that target class variable is a descriptor, use its __set__ to update the value
        if hasattr(target, '__set__'):
            target.__set__(instance, self._writer(value))
        # Otherwise, just change the value
        else:
            setattr(instance, self.attr_name, self._writer(value))

    @staticmethod
    def _writer(value):
        """
        Default writer function to translate a value to a format to be written to the database.
        Passed a value from the application in the param `value`, and must return a value to be
        written to the database. Use cases include hashing a password for storage in a database.
        """
        return value

    def writer(self, func):
        """ Decorator to override the attribute's writer (translator) function """
        self._writer = func
        return self

    def check_authorization(self, request, auth_func=None):
        if not auth_func:
            auth_func = self.auth

        if not auth_func:
            return True

        # An auth function could take an auth context, a context and a target
        # that we're authorizing against, or nothing at all. Try to provide the
        # right parameters based on the number of params the function has
        auth_func_param_names = func_params(auth_func)
        if not auth_func_param_names:
            auth_function_out = exec_function(auth_func)
        elif len(auth_func_param_names) == 1:
            auth_function_out = exec_function(auth_func, AuthContext(request))
        else:
            auth_function_out = exec_function(auth_func, AuthContext(request), self.cls)

        if isinstance(auth_function_out, collections.Sequence):
            # We got a list of stuff (since the lambdas returns are designed
            # to be compatible with SQLAlchemy filters, i.e. the lambda might
            # be like "condition1, condition2, condition3"). If this is a list
            # of booleans, flatten it
            if all([isinstance(x, bool) for x in auth_function_out]):
                auth_function_out = all(auth_function_out)

        return auth_function_out

    def is_visible(self, request):
        """
        Combines the "readable" attribute with dynamic attribute limitations (i.e.
        if this is a dynamic attribute and not all of its required paramters are
        specified in the request, this attribute cannot be displayed)
        """
        if not self.readable:
            return False
        for param in self.dynamic_params:
            if param['name'] not in request.GET:
                return False
            if self.check_authorization(request) is False:
                return False
            param['validator'].validate(request.GET[param['name']])
        return True


class APIValidator(object):
    def validate(self, value):
        """
        Dummy validator function
        """
        pass

    def validator(self, func):
        """
        Decorator to change the class's validate function
        """
        obj = self
        obj.validate = func
        return obj

    def extend(self, func):
        """
        Decorator to change the class's validate function. This will
        use the class's existing validate function, and then perform
        func on top of it.
        """
        old_validator = object.__getattribute__(self, 'validate')
        def new_validator(*args, **kwargs):
            old_validator(*args, **kwargs)
            func(*args, **kwargs)
        obj = self
        obj.validate = new_validator
        return obj

    def __init__(self, func=None):
        # If func is specified, we will use it as the validation function
        if func:
            self.validate = func

    # The following two functions are an ugly hack so that we can override
    # validatorobj.validate, but if that happens to be a lambda from the API
    # config (in the form of a string) and something tries to call it, it won't
    # freak out (because strings obviously aren't callable)
    def _exec_validator(self, value):
        exec_function(object.__getattribute__(self, 'validate'), value)

    def __getattribute__(self, key):
        if key == 'validate':
            return self._exec_validator
        else:
            return object.__getattribute__(self, key)


class APIReader(object):
    def read(self, value):
        pass


# class ResourceRegistry(type):
#     """ Maintains a list of declared APIResource classes """
#     def __init__(cls, name, bases, attrs):
#         if not hasattr(cls, 'resources'):
#             # This is a new registry... Set up an empty list
#             cls.resources = []
#         else:
#             # This must be an APIResource class
#             cls.resources.append(cls)


class APIResource(object):

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime)

    __request__ = None    # Pyramid request object should be set by traversal parent

    # re 6/18/15 this is a really ugly hack to set the __request__ attribute
    # when the object wasn't produced via traversal, but was instead loaded by
    # SQLAlchemy and is now being used in the API. In this case, there would be
    # no parent that we have control over to set __request__, but the resource
    # might still try to use that... Pyramid strongly discourages use of
    # get_current_request, so a different solution would be better
    @orm.reconstructor
    def load_request(self):
        self.__request__ = get_current_request()

    @classmethod
    def primary_key_name(cls):
        return cls.__mapper__.primary_key[0].key

    @classmethod
    def get_api_config(cls, *args):
        log.debug('Getting API config for {} at {}'.format(cls, args))
        target = api_config()[cls.__name__]
        for key in args:
            log.debug('Recursing into {}...'.format(key))
            if target is None:
                raise KeyError('Cannot get {} from target None'.format(key))
            target = target[key]
        return target

    @classmethod
    def get_api_attr(cls, name):
        return next(attr for attr in cls.get_api_config('attrs') if attr.key == name)

    def check_authorization(self, request, auth_func, raise_exc=True):
        if not auth_func:
            # No auth func specified
            return True

        # An auth function could take an auth context, a context and a target
        # that we're authorizing against, or nothing at all. Try to provide the
        # right parameters based on the number of params the function has
        auth_func_param_names = func_params(auth_func)
        if not auth_func_param_names:
            auth_function_out = exec_function(auth_func)
        elif len(auth_func_param_names) == 1:
            auth_function_out = exec_function(auth_func, AuthContext(request))
        else:
            auth_function_out = exec_function(auth_func, AuthContext(request), self)

        if isinstance(auth_function_out, collections.Sequence):
            # We got a list of booleans (since the lambdas returns are designed
            # to be compatible with SQLAlchemy filters, i.e. the lambda might
            # be like "condition1, condition2, condition3"). Convert this to
            # "condition1 and condition2 and condition3"
            auth_function_out = all(auth_function_out)

        if not auth_function_out:
            if raise_exc:
                raise ResourceException(403,
                                        'unauthorized_caller',
                                        'You do not have sufficient privileges to perform ' + \
                                        'this action.')
            return False
        if auth_function_out is not True:
            log.warning('The auth function for {} returned a non-boolean value!', self)
        
        return True

    @classmethod
    def create(cls, post_params, parent, request, defaults={}):
        """
        Create an instance of this resource, using the information contained in the post_params
        dictionary. This method will cycle through the fields mandated in api config create,
        ensuring these keys are present in the post_params dictionary and that the values all pass
        validation, and then it will validate any optional fields defined there.  After each
        key/value passes validation, it will be added to init_params, and after all validation is
        complete, an instance of the class will be created, and the init_params dictionary
        will be passed to its __init__ function as a kwarg dictionary. Returns created object.
        """
        log.debug("Creating new {}".format(cls.__name__))
        # Create a dictionary used to hold the parameters and values that will be passed
        # to the resource object's __init__ function after validation succeeds
        init_params = {}

        required_fields = cls.get_api_config('create', 'required_fields')
        optional_fields = cls.get_api_config('create', 'optional_fields')

        # If the parent collection supplies defaults, remove them from the acceptable fields
        for key, value in defaults.iteritems():
            if key in required_fields:
                required_fields.remove(key)
            if key in optional_fields:
                optional_fields.remove(key)
            init_params[key] = value

        # Go through mandatory parameters
        for field in required_fields:
            if field not in post_params:
                raise ResourceException(400, 'bad_'+field, 'The %s field is mandatory.' % field)
            # Get APIAttribute object
            attr = cls.get_api_attr(field)
            # Validate the specified value
            attr.validator.validate(post_params[field])
            # Add to init_params to be passed to object __init__ on creation
            init_params[field] = post_params[field]
            post_params.pop(field)

        # Go through optional parameters
        for field in optional_fields:
            if field in post_params:
                # Get APIAttribute object
                attr = cls.get_api_attr(field)
                # Validate the new value
                attr.validator.validate(post_params[field])
                # Add to init_params to be passed to object __init__ on creation
                init_params[field] = post_params[field]
                post_params.pop(field)

        # Check if there were any unidentified parameters sent
        if post_params:
            raise ResourceException(status_code=400, error_id="unrecognized_fields",
                                    message="The following key(s) are not recognized fields " + \
                                            "for this resource: %s. No data has been modified." \
                                            % ', '.join(post_params.keys()))

        # Create and return object
        log.debug("Calling {} constructor".format(cls.__name__))
        obj = cls.__new__(cls)
        obj.__traversal_parent__ = parent
        obj.__request__ = request
        obj.__init__(**init_params)
        log.debug("Created {} {}".format(cls.__name__, obj))
        return obj

    def __json__(self, request):
        """
        Creates and returns a dictionary with all keys and values of this resource's
        public attributes, for rendering to JSON (used in GET requests)
        """
        default_attrs = [APIAttribute('active', writable=False, cls=self.__class__),
                         APIAttribute('created_at', writable=False,
                                      reader=lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ") if x
                                                       else None,
                                      cls=self.__class__),
                         APIAttribute('updated_at', writable=False,
                                      reader=lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ") if x
                                                       else None,
                                      cls=self.__class__),
                         APIAttribute('deleted_at', writable=False,
                                      reader=lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ") if x
                                                       else None,
                                      cls=self.__class__)]
        return { attr.key:attr.read(self) for attr
                                          in default_attrs + self.get_api_config('attrs')
                                          if attr.is_visible(self.__request__)
                                          and self.check_authorization(self.__request__, attr.auth, raise_exc=False) }

    def __getitem__(self, key):
        log.info('Getting key {} on {}...'.format(key, self))
        if key not in self.get_api_config('children').keys():
            # other_actions = self.get_api_config()
            # [other_actions.pop(key, None) for key in ['group_name', 'attrs', 'children',
            #                                           'list', 'create', 'read', 'update',
            #                                           'delete', 'auth']]
            # dynamic_subpaths = [ action['url'] for key, action in other_actions.iteritems()
            #                      if 'url' in action ]
            # from pprint import pformat
            # raise Exception(pformat(dynamic_subpaths))
            raise ResourceException(404,
                                     'child_not_found',
                                     'No child "%s" could be found in this resource.' \
                                     % key)
        target = self.get_api_config('children', key)
        if isinstance(target, dict):
            # Child is a subcollection
            log.info('The requested key is a subcollection. Authorizing...')
            self.check_authorization(self.__request__, target['auth'])
            log.info('Returning...')
            target = APICollection(target['references'], parent=self,
                                   secondary=target.get('secondary', None),
                                   default_pk=target.get('default_pk', None),
                                   defaults=target.get('defaults', {}),
                                   foreign_key=target.get('foreign_key', None),
                                   association_handler=target.get('association_handler', None),
                                   disassociation_handler=target.get('disassociation_handler',
                                                                     None),
                                   delete_behavior=target.get('delete_behavior', 'delete'),
                                   **target.get('filters', {}))
            target.__traversal_parent__ = self
            target.__request__ = self.__request__
            return target
        else:
            # Child is a child resource
            log.info('The requested key is a direct APIResource. Returning...')
            # Set parent reference, so resource can be context-sensitive
            item = getattr(self, key)
            item.__traversal_parent__ = self
            item.__request__ = self.__request__
            return item

    def update(self, post_params):
        """
        Updates one or more of the resource's attributes using information in the post_params
        dictionary.
        """
        log.debug('Updating {}'.format(self))
        writable_attrs = { attr.key:attr for attr
                                         in self.get_api_config('attrs')
                                         if attr.writable }
        # See if there's any submitted fields that aren't attributes of the resource
        unrecognized_keys = set(post_params.keys()) - set(writable_attrs.keys())
        if unrecognized_keys:
            raise ResourceException(400,
                                    'unrecognized_fields',
                                    'The following key(s) are not valid updatable attributes ' + \
                                    'of this resource: %s. No data has been modified.' \
                                    % ', '.join(unrecognized_keys))
        # Figure out what we're going to be updating
        keys_to_update = set(writable_attrs.keys()).intersection(post_params.keys())
        if not keys_to_update:
            raise HTTPNotModified
        # Validate all the changes before making any of them
        for key in keys_to_update:
            try:
                writable_attrs[key].validator.validate(post_params[key])
            except ResourceException as e:
                e.message = e.message.strip() + ' No data has been modified.'
                raise e
        # Try updating
        for key in keys_to_update:
            writable_attrs[key].write(self, post_params[key])
            # Mark this resource as updated
            self.updated_at = datetime.utcnow()
        log.debug('Successfully updated {}'.format(self))
        return ResourceUpdated()

    def delete(self):
        """
        Marks this resource as deleted.
        """
        if self.__traversal_parent__.delete_behavior == 'disassociate':
            log.debug('Disassociating {} from {}'.format(self, self.__traversal_parent__))
            self.__traversal_parent__.disassociation_handler(self,
                                                             self.__traversal_parent__.parent,
                                                             self.__request__)
        else:
            log.debug('Deleting {}'.format(self))
            self.active = False
            self.deleted_at = datetime.utcnow()


class RegistryMeta(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'resources'):
            cls.resources = []
        elif name != 'VirtualResource':
            cls.resources.append(cls)


class VirtualResourceRegistry:
    __metaclass__ = RegistryMeta


class VirtualResource(APIResource, VirtualResourceRegistry):

    @classmethod
    def primary_key_name(cls):
        return 'id'

    def __json__(self, request):
        return { attr.key:attr.read(self) for attr
                                          in self.get_api_config('attrs')
                                          if attr.is_visible(self.__request__) }


class APICollection(object):
    """ Represents a collection of API resource objects """
    __request__ = None    # Pyramid request object should be set by traversal parent

    def __init__(self, resource, parent=None, secondary=None, foreign_key=None,
                 default_pk=None, defaults={}, filters=[], association_handler=None,
                 disassociation_handler=None, delete_behavior='delete',
                 sort_by=None, sort_dir=None, **kwargs):
        """
        Sets up a resource collection for the specified resource. Constraints can be
        placed on the contents of this resource by setting kwargs (e.g.
        APICollection(User, first_name='bob') will only contain users whose names are
        bob). Keys in kwargs must match the class attribute names of the resource
        classes.
        """
        log.debug('Entering a {} collection'.format(resource))
        if isinstance(resource, basestring):
            resource = get_resource(resource)
        self.resource = resource
        # Prepare the SQLAlchemy query that will be used based on parent
        if parent:
            # We need to assemble relationship between the parent class and the child
            # class and make sure only the parent's children show up in this collection.
            # Get the target Column from the registry of all foreign keys that point to the
            # primary key of parent.__tablename__ (i.e. all child foreign keys)
            parent_primary_key = parent.primary_key_name()
            parent_fk_registry = parent.__table__.metadata._fk_memos[(parent.__tablename__,
                                                                      parent_primary_key)]
            matching_columns = [ fk_memo.parent for fk_memo in parent_fk_registry
                                 if fk_memo.parent.table.name == resource.__tablename__ ]
            if not matching_columns:
                # Bummer. No matching columns found.
                if secondary:
                    # Try a many-to-many
                    if isinstance(secondary, basestring):
                        secondary = next(cls for cls in resource_registry() if
                                         cls.__name__ == secondary)
                    parent_matching = [ fk_memo.parent for fk_memo in parent_fk_registry
                                        if fk_memo.parent.table.name == secondary.__tablename__ ]
                    if not parent_matching:
                        raise ValueError('No ForeignKey in {} could be found referencing {}.{}.'.format(
                                          secondary.__tablename__, parent.__tablename__,
                                          parent_primary_key))
                    elif len(parent_matching) > 1:
                        raise ValueError('More than one ForeignKey links {} and {}.'.format(
                                         secondary, parent))
                    # Okay, we have a link parent-secondary. Time to get secondary-resource
                    child_primary_key = resource.primary_key_name()
                    child_fk_registry = resource.__table__.metadata \
                                                ._fk_memos[(resource.__tablename__,
                                                            child_primary_key)]
                    child_matching = [ fk_memo.parent for fk_memo in child_fk_registry
                                       if fk_memo.parent.table.name == secondary.__tablename__ ]
                    if not child_matching:
                        raise ValueError('No ForeignKey in {} could be found referencing {}.{}.'.format(
                                          secondary.__tablename__, resource.__tablename__,
                                          child_primary_key))
                    elif len(parent_matching) > 1:
                        raise ValueError('More than one ForeignKey links %r and %r.' %
                                         (secondary, resource))
                    # We have a link!
                    log.debug('Found many-to-many link %s.%s <--> %r, %r <--> %s.%s',
                              parent.__class__.__name__, parent_primary_key,
                              parent_matching[0], child_matching[0],
                              resource.__name__, child_primary_key)
                    query_target = [resource, secondary, parent.__class__]
                    query_constraints = [getapiattr(resource, child_primary_key).get_class_attr(self.__request__)==child_matching[0],
                                         parent_matching[0]==getapiattr(parent, parent_primary_key).get_class_attr(self.__request__)]
                else:
                    raise ValueError('No ForeignKey in %r could be found referencing %r.%r.' %
                                     (resource.__tablename__, parent.__tablename__,
                                      parent_primary_key))
            elif len(matching_columns) > 1:
                # More than one ForeignKey links the parent and child tables.
                if foreign_key:
                    try:
                        fk = next(col for col in matching_columns if col.key == foreign_key)
                    except StopIteration:
                        raise ValueError('ForeignKey %r referencing %r was not found in %r.' % \
                                         (foreign_key, parent, resource))
                    else:
                        query_target = [resource, parent.__class__]
                        query_constraints = [fk == getapiattr(parent, parent_primary_key).get_class_attr(self.__request__)]
                else:
                    raise ValueError('More than one ForeignKey links %r and %r. ' \
                                     % (resource, parent) \
                                     + 'Try specifying the foreign_key argument.')
            else:
                # Cool, we found the ForeignKey.
                log.debug('Found target column %r' % matching_columns[0])
                query_target = [resource, parent.__class__]
                query_constraints = [matching_columns[0]==getapiattr(parent, parent_primary_key).get_class_attr(self.__request__)]
        else:
            query_target = [resource]
            query_constraints = []
        # Add constraints based on filters, sort, and kwargs
        query_constraints.append(getattr(resource, 'active') == (True))
        for key, value in kwargs.iteritems():
            try:
                query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__) == value)
            except AttributeError:
                raise AttributeError("Class {} has no attribute {}.".format(resource.__name__, key))
        for key, op, value in filters:
            target_attr = next((attr for attr in resource.get_api_config()['attrs'] if attr.is_visible(self.__request__) and attr.key == key), None)
            target_attr_auth = target_attr.check_authorization(self.__request__) if target_attr else False
            if isinstance(target_attr_auth, bool) and not target_attr_auth:
                raise ResourceException(400, 'bad_query_key',
                    'This resource has no filterable attribute \"{}\".'.format(key))
            else:
                # The attribute's auth function returned a SQLAlchemy
                # filter. We don't want people to be able to filter by
                # things they're not supposed to be able to see, so filter
                # the results by this
                if isinstance(target_attr_auth, collections.Sequence):
                    query_constraints.extend(target_attr_auth)
                else:
                    query_constraints.append(target_attr_auth)
            try:
                if op == ':':
                    query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__).like(value))
                elif op == '=':
                    query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__) == value)
                elif op == '<':
                    query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__) < value)
                elif op == '>':
                    query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__) > value)
                elif op == '<=':
                    query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__) <= value)
                elif op == '>=':
                    query_constraints.append(getapiattr(resource, key).get_class_attr(self.__request__) >= value)
                else:
                    raise ValueError('The operator %r is invalid' % op)
            except AttributeError:
                raise AttributeError("Class {} has no attribute {}.".format(resource.__name__, key))
        # sort_by support
        if sort_by:
            target_attr = next((attr for attr in resource.get_api_config()['attrs'] if attr.is_visible(self.__request__) and attr.key == sort_by), None)
            target_attr_auth = target_attr.check_authorization(self.__request__) if target_attr else False
            if isinstance(target_attr_auth, bool) and not target_attr_auth:
                raise ResourceException(400, 'bad_sort_by',
                    'This resource has no sortable attribute \"{}\".'.format(sort_by))
            else:
                # The attribute's auth function returned a SQLAlchemy
                # filter. We don't want people to be able to sort by
                # things they're not supposed to be able to see, so filter
                # the results by this
                if isinstance(target_attr_auth, collections.Sequence):
                    query_constraints.extend(target_attr_auth)
                else:
                    query_constraints.append(target_attr_auth)
        else:
            sort_by = resource.primary_key_name()
        # sort_dir support
        if not sort_dir or sort_dir.lower() in ['asc', 'a', 'ascending']:
            query_order_by = getapiattr(resource, sort_by).get_class_attr(self.__request__)
        elif sort_dir.lower() in ['desc', 'd', 'descending']:
            query_order_by = getapiattr(resource, sort_by).get_class_attr(self.__request__).desc()
        else:
            raise ResourceException(400, 'bad_sort_dir',
                '\"{}\" is not a valid sort direction.'.format(sort_dir))
        # Construct SQLA query
        self.query_target = query_target
        self.query = sqla_session().query(query_target[0])
        if len(query_target) > 1:
            for target in query_target[1:]:
                self.query = getattr(self.query, 'join')(target)
        self.query_constraints = query_constraints
        self.query_order_by = query_order_by
        # Save defaults
        self.defaults = defaults
        if default_pk:
            self.defaults[default_pk] = getattr(parent, parent_primary_key)
        # Save handlers
        self.association_handler = association_handler
        self.disassociation_handler = disassociation_handler
        # Save other info
        self.parent = parent
        if delete_behavior not in ('delete', 'disassociate'):
            raise ValueError('The delete_behavior {} is invalid.'.format(delete_behavior))
        self.delete_behavior = delete_behavior
        # Celebrate
        # log.info('Created APICollection for %r with filter %r' % (self.resource,
        #     { exp:exp.__dict__ for exp in self.query_constraints }))
        # log.info('%r' %self.items)

    def add(self, resource, key):
        if self.association_handler:
            log.debug('Calling association handler for {}'.format(self))
            with transaction.manager:
                self.association_handler(resource, self.parent, self.__request__)
            log.debug('Association handler called')
            return ResourceUpdated()
        else:
            raise ResourceException(404,
                                    'resource_not_found',
                                    'No resource "%s" could be found in this collection.' \
                                    % key)

    @property
    def items(self):
        return self.query.filter(*self.query_constraints) \
                   .order_by(self.query_order_by).all()

    def __eq__(self, x):
        return self.items == x

    def __getitem__(self, key):
        DBSession = sqla_session()
        item = DBSession.query(self.resource).get(key)
        if item is None or (item not in self.items and self.__request__.method != 'PUT'):
            raise ResourceException(404,
                                     'resource_not_found',
                                     'No resource "%s" could be found in this collection.' \
                                     % key)
        elif item not in self.items and self.__request__.method == 'PUT':
            # Try associating adding the resource to this collection
            return self.add(DBSession.query(self.resource).get(key), key)
        else:
            # Set parent reference, so resource can be context-sensitive
            item.__traversal_parent__ = self
            item.__request__ = self.__request__
            return item

    def __json__(self, request):
        """ List resources in collection """
        auth_function = self.resource.get_api_config('list', 'auth')
        # Get SQLAlchemy constraints to apply based on read-context authorization
        if not auth_function:
            filters = self.query_constraints
        else:
            # An auth function could take an auth context, a context and a target
            # that we're authorizing against, or nothing at all. Try to provide the
            # right parameters based on the number of params the function has
            auth_func_param_names = func_params(auth_function)
            if not auth_func_param_names:
                auth_function_out = exec_function(auth_function)
            elif len(auth_func_param_names) == 1:
                auth_function_out = exec_function(auth_function, AuthContext(request))
            else:
                auth_function_out = exec_function(auth_function, AuthContext(request), self.resource)

            if auth_function_out is True:
                # There is no auth function, or it's passive (returns True)
                filters = self.query_constraints
            elif auth_function_out is False:
                # There is no auth function, or it's passive (returns False)
                return []
            elif isinstance(auth_function_out, collections.Sequence):
                # Auth function returned a list or tuple of constraints
                filters = self.query_constraints + list(auth_function_out)
            else:
                # Auth function returned a single constraint
                filters = self.query_constraints + [auth_function_out]

        # Return filtered set of items for JSON serialization
        items = self.query.filter(*filters).order_by(self.query_order_by).all()
        for item in items:
            item.__traversal_parent__ = self
            item.__request__ = self.__request__
        return items

    def check_authorization(self, request, auth_func):
    #     if not auth_func:
    #         return
    #
    #     # An auth function could take an auth context, a context and a target
    #     # that we're authorizing against, or nothing at all. Try to provide the
    #     # right parameters based on the number of params the function has
    #     auth_func_param_names = func_params(auth_func)[1:]
    #     if not auth_func_param_names:
    #         auth_function_out = exec_function(auth_func)
    #     elif len(auth_func_param_names) == 1:
    #         auth_function_out = exec_function(auth_func, AuthContext(request))
    #     else:
    #         auth_function_out = exec_function(auth_func, AuthContext(request), self)
    #
    #
    #     constraints = auth_function_out
    #     if not isinstance(constraints, collections.Sequence):
    #         constraints = [constraints]
    #     if user not in DBSession.query(User).filter(*constraints).all():
    #         raise ResourceException(403,
    #                                 'unauthorized_caller',
    #                                 'You do not have sufficient privileges to perform ' + \
    #                                 'this action.')
        # TODO: Is there any time when a root collection should *not* be authorized?
        return True


class VirtualCollection(object):
    def __init__(self, resource):
        if isinstance(resource, basestring):
            log.debug('Looking up target class %r in resource registry...', resource)
            resource = next(cls for cls in resource_registry() if cls.__name__ == resource)
            log.debug('Found %r in resource registry' % resource)
        self.resource = resource

    def __getitem__(self, key):
        target = self.resource.__new__()
        target.__traversal_parent__ = self
        target.__request__ = self.__request__
        target.__init__(key)
        return target


class APISession(object):
    @property
    def expires(self):
        return self.updated_at + timedelta(seconds=session_duration())

    @property
    def is_valid(self):
        return self.active and self.expires >= datetime.utcnow()

    def touch(self):
        self.updated_at = datetime.utcnow()


class ContextPredicate(object):
    """
    Pyramid view predicate for controlling resource/collection usage
    in list, create, read, update, and delete API contexts. Used in
    Pyramid view configuration to easily limit access to resources
    and collections if they do not have a context enabled in their
    __api_config__ dictionaries.  See http://goo.gl/EerpA0
    """
    def __init__(self, val, config):
        """
        Sets up a ContextPredicate to limit access to a certain API context,
        specified in val. E.g. view_config(api_context='list') will call
        ContextPredicate('list', <Configurator instance>)
        """
        if val not in ('list', 'create', 'read', 'update', 'delete'):
            raise ValueError('%r is not a valid API context.' % val)
        self.val = val

    def text(self):
        return 'api_context = %s' % (self.val,)

    phash = text

    def __call__(self, context, request):
        if isinstance(context, APIResource):
            return True if context.get_api_config(self.val) else False
        elif isinstance(context, APICollection):
            return True if context.resource.get_api_config(self.val) else False
        else:
            raise TypeError('ContextPredicate got unexpected context %r; ' % context \
                          + 'was expecting an APIResource or APICollection')

def check_access_token(request):
    if hasattr(request, 'sofa_access_token_verified'):
        return request.sofa_session

    if 'Authorization' not in request.headers:
        raise ResourceException(401,
                                'authentication_required',
                                'You must be authenticated to perform this action.')
    elif 'Authorization' in request.headers \
      and request.headers['Authorization'].split(None, 1)[0].lower() != 'token':
        raise ResourceException(400,
                                'bad_authorization_scheme',
                                'The "%s" authorization scheme is not supported. ' \
                                % request.headers['Authorization'].split(None, 1)[0] \
                                + 'Please use an authentication token from /sessions.')
    # Check the session ID
    session_id = request.headers['Authorization'].split(None, 1)[-1]
    session = session_lookup_func()(session_id)
    if not session or not session.is_valid:
        raise ResourceException(400,
                                'bad_access_token',
                                'The access token in the Authorization ' + \
                                'header is invalid or expired.')
    # Make sure the session hasn't expired
    if session.expires < datetime.utcnow():
        raise ResourceException(401,
                                'expired_access_token',
                                'The access token in the Authorization ' + \
                                'header has expired.')
    # Someone is using this session, so let's touch it
    session.touch()
    request.sofa_access_token_verified = True
    request.sofa_session = session
    return session


class AuthContext(object):
    """ Contains the context for authorization """

    @property
    def session_id(self):
        return self.session.id if self.session else None

    def __init__(self, request):
        # Set caller info
        if 'Authorization' not in request.headers:
            self.session = None
            self.caller_id = None
            self.caller_type = None
            self.user_type = None
        else:
            self.session = check_access_token(request)
            self.caller_id = self.session.user_id
            self.caller_type = 'user'
            if hasattr(self.session, 'user_type'):
                self.user_type = self.session.user_type
            else:
                self.user_type = None
        # Set request info
        self.http_method = request.method
        self.params = request.params
        self.request = request

    def __repr__(self):
        return "<AuthContext(caller=%r, method=%r, params=%r)>" \
                % (self.caller_id, self.http_method, self.params)
