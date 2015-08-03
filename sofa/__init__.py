import logging
log = logging.getLogger(__name__)

from structure import (
    APIAttribute,
    APIValidator,
    APIResource,
    APICollection,
    APISession,
    VirtualResourceRegistry,
    VirtualResource,
    resource_registry,
    AuthContext,
    )
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
from readers import (
    DateReader,
    DatetimeReader,
    )
from config import (
    load_api_config,
    api_config,
    collection_class_map,
    get_class_name,
    )
from responses import (
    ResourceCreated,
    ResourceUpdated,
    ResourceDeleted,
    ResourceException,
    )
from tree import Root as TraversalRoot

def includeme(config):
    from structure import ContextPredicate
    config.add_view_predicate('api_context', ContextPredicate)
    config.add_view('sofa.views.nopath_view', context=TraversalRoot, renderer='json')
    config.add_view('sofa.views.updated_view', context=ResourceUpdated, renderer='json')
    config.add_view('sofa.views.CollectionViews', attr='get', context=APICollection,
                    renderer='json', request_method='GET', api_context='list')
    config.add_view('sofa.views.CollectionViews', attr='post', context=APICollection,
                    renderer='json', request_method='POST', api_context='create')
    config.add_view('sofa.views.CollectionViews', attr='other_verb', context=APICollection,
                    renderer='json')
    config.add_view('sofa.views.ResourceViews', attr='get', context=APIResource,
                    renderer='json', request_method='GET', api_context='read')
    config.add_view('sofa.views.ResourceViews', attr='put', context=APIResource,
                    renderer='json', request_method='PATCH', api_context='update')
    config.add_view('sofa.views.ResourceViews', attr='delete', context=APIResource,
                    renderer='json', request_method='DELETE', api_context='delete')
    config.add_view('sofa.views.ResourceViews', attr='other_verb', context=APIResource,
                    renderer='json')
    config.add_view('sofa.views.resource_exception_view', context=ResourceException,
                    renderer='json')

def configure(sqla_session=None, api_config_path=None, session_lookup_func=None):
    if sqla_session:
        config.set_sqla_session(sqla_session)
    if api_config_path:
        config.load_api_config(api_config_path)
    if session_lookup_func:
        config.set_session_lookup_func(session_lookup_func)
