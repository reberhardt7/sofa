import logging
log = logging.getLogger(__name__)

# TODO: ResourceCreated, ResourceUpdated, and ResourceDeleted can be combined
# into one class: ResourceResponse
class ResourceCreated(object):
    """
    Usage: return ResourceCreated()
    """
    def __init__(self, resource_id, message='Resource created.', data="null"):
        self.status_code = 201
        self.resource_id = resource_id
        self.message = message
        self.data = data

    def __json__(self, request):
        request.response.status_int = self.status_code
        request.response.status = "201 Created"

        return {'statusCode': self.status_code,
                'resourceID': self.resource_id,
                'message': self.message}


class ResourceUpdated(object):
    """
    Usage: return ResourceUpdated()
    """
    def __init__(self, message='Resource updated.'):
        self.status_code = 200
        self.message = message

    def __json__(self, request):
        request.response.status_int = 200
        request.response.status = "200 OK"

        return {'statusCode': 200,
                'errorID': 'resource_updated',
                'message': self.message}


class ResourceDeleted(object):
    """
    Usage: return ResourceDeleted()
    """
    def __init__(self, message='Resource deleted.'):
        self.status_code = 200
        self.message = message

    def __json__(self, request):
        request.response.status_int = 200
        request.response.status = "200 OK"

        return {'statusCode': 200,
                'errorID': 'resource_deleted',
                'message': self.message}


class ResourceException(Exception):
    """
    Usage: raise ResourceException(status_code, 'error_id', 'message') in views,
           return ResourceException(status_code, 'error_id', 'message') in models
    """
    def __init__(self, status_code, error_id, message):
        log.debug("ResourceException({}, {}): {}".format(status_code, error_id, message))
        if status_code not in (304, 400, 401, 403, 404, 422, 500):
            raise ValueError("%s is not a valid status code" % status_code)
        self.status_code = status_code
        self.error_id = error_id
        self.message = message
