import re

from config import root_collections, get_class_name
from responses import ResourceException
from structure import APICollection, VirtualCollection

import logging
log = logging.getLogger(__name__)

class Root(object):
    def __init__(self, request):
        self.request = request

    def __getitem__(self, key):
        if key in root_collections():
            # Find the class that this collection maps to
            clsName = get_class_name(key)

            # Use the querystring (?q=) from the GET params to create a list of
            # filters that should be applied to the database query. An example
            # querystring is ?q=name:Ryan,user_type=admin which will search for
            # users with `user_type` exactly equal to "admin" and `name`
            # containing "Ryan."
            querystring_re = re.compile(r'^(.*?)(?<!\\)(:|=|<=|>=|<|>)(.*?)$')
            querystrings = re.split(r'(?<!\\),', self.request.GET['q']) if 'q' in self.request.GET and self.request.GET['q'] else []
            filters = []
            for q in querystrings:
                if not querystring_re.match(q):
                    raise ResourceException(400, 'bad_query', 'The query string in the GET parameter is malformed.')
                k, op, v = querystring_re.match(q).groups()
                if querystring_re.match(k) or querystring_re.match(v):
                    raise ResourceException(400, 'bad_query',
                        'The query string in the GET parameter is malformed. '
                        'Colon or equal signs must be escaped.')
                filters.append((k, op, v))

            # Support sort_by and sort_dir GET params
            sort_by = self.request.GET.get('sort_by', None)
            sort_dir = self.request.GET.get('sort_dir', None)

            # Create APICollection
            target = APICollection.__new__(APICollection)
            target.__traversal_parent__ = self
            target.__request__ = self.request
            target.__init__(clsName, filters=filters,
                            sort_by=sort_by, sort_dir=sort_dir)
            return target
        else:
            raise ResourceException(status_code=404, error_id="v0-404",
                                    message='The root resource type ' + key + ' could not be found. Available ' \
                                        + 'root resource types are: %s' % ', '.join(root_collections()))
