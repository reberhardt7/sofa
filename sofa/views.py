from config import sqla_session, root_collections
from tree import Root
from responses import (
    ResourceCreated,
    ResourceUpdated,
    ResourceDeleted,
    ResourceException,
    )
from structure import APICollection, APIResource

# Called if there is no path passed to the root traversal tree
# Tell the user they need to specify a resource
def nopath_view(request):
    raise ResourceException(status_code=404, error_id="v0-404",
                            message=('You must specify a root resource type '
                                     '(e.g. /{}). Available '
                                     'resource types are: {}').format(
                                     root_collections()[0] if root_collections() else 'resource',
                                     ','.join(root_collections())))

def updated_view(request):
    return request.context


class CollectionViews(object):
    def __init__(self, request):
        self.request = request

    def get(self):
        # Make sure the caller is authorized to list
        self.request.context.check_authorization(self.request,
            self.request.context.resource.get_api_config('list', 'auth'))
        # OK, return the stuff
        return self.request.context

    def post(self):
        """ Create a new instance of the given resource """
        DBSession = sqla_session()
        # Make sure the caller is authorized to create
        self.request.context.check_authorization(self.request,
            self.request.context.resource.get_api_config('create', 'auth'))
        # OK, create the resource
        resource = self.request.context.resource.create(self.request.POST,
                                                        self,
                                                        self.request,
                                                        self.request.context.defaults)
        DBSession.add(resource)
        DBSession.flush()
        primary_key_name = resource.primary_key_name()
        primary_key_value = getattr(resource, primary_key_name)
        return ResourceCreated(primary_key_value)

    def other_verb(self):
        context_verb_map = {'list': 'GET',
                            'create': 'POST'}
        allowed_verbs = [ context_verb_map[c] for c in ['list', 'create']
                                              if self.request.context.resource.get_api_config(c) ]
        if len(allowed_verbs) == 2:
            allowed_string = 'only GET or POST to'
        elif len(allowed_verbs) == 1:
            allowed_string = 'only %s to' % allowed_verbs[0]
        else:
            allowed_string = 'not use'

        raise ResourceException(status_code=400, error_id="bad_verb",
                                message="This URL does not support the use of the HTTP " + \
                                        "%s verb. You may %s this URL." % (self.request.method,
                                        allowed_string))


class ResourceViews(object):
    def __init__(self, request):
        self.request = request

    def get(self):
        # Make sure the caller is authorized to read
        self.request.context.check_authorization(self.request,
            self.request.context.get_api_config('read', 'auth'))
        # OK, return the stuff
        return self.request.context

    def put(self):
        """ Update this resource """
        # Make sure the caller is authorized to update
        self.request.context.check_authorization(self.request,
            self.request.context.get_api_config('update', 'auth'))
        # OK, update the resource
        self.request.context.update(self.request.POST)
        return ResourceUpdated()

    def delete(self):
        """ Mark this resource as inactive """
        # Make sure the caller is authorized to delete
        self.request.context.check_authorization(self.request,
            self.request.context.get_api_config('delete', 'auth'))
        # OK, delete the resource
        self.request.context.delete()
        return ResourceDeleted()

    def other_verb(self):
        context_verb_map = {'read': 'GET',
                            'update': 'PATCH',
                            'delete': 'DELETE'}
        allowed_verbs = [ context_verb_map[c] for c in ['read', 'update', 'delete']
                                              if self.request.context.get_api_config(c) ]
        if len(allowed_verbs) == 3:
            allowed_string = 'only GET, PATCH, or DELETE to'
        elif len(allowed_verbs) == 2:
            allowed_string = 'only %s or %s to' % (allowed_verbs[0], allowed_verbs[1])
        elif len(allowed_verbs) == 1:
            allowed_string = 'only %s to' % allowed_verbs[0]
        elif len(allowed_verbs) == 0:
            allowed_string = 'not use'

        raise ResourceException(status_code=400, error_id="bad_verb",
                                message="This URL does not support the use of the HTTP " + \
                                        "%s verb. You may %s this URL." % (self.request.method,
                                        allowed_string))


def resource_exception_view(exc, request):
    statuses = {304:"304 Not Modified",
                400:"400 Bad Request",
                401:"401 Unauthorized",
                403:"403 Forbidden",
                404:"404 Not Found",
                422:"422 Unprocessable Entity",
                500:"500 Internal Server Error"}

    request.response.status_int = exc.status_code
    request.response.status = statuses[exc.status_code]

    return {'statusCode': exc.status_code,
            'errorID': exc.error_id,
            'message': exc.message}
