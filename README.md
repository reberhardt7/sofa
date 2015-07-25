sofa
====
A simple Python REST API framework

About Sofa
----------
Sofa is a lightweight REST API framework written in Python for Pyramid and
SQLAlchemy. It is intended to integrate with an existing Pyramid application
so that you can keep your database models and backend code the way you are
used to without needing to learn the way an entirely new framework deals with
all of that. You can even keep your own views, if you would like; Sofa simply
adds a new set of views at a path of your choosing.

Where possible, Sofa focuses on being declarative over imperative. It would
rather have you tell it what you want your API to look like and let it figure
out the rest. At the same time, Sofa strives for flexibility. If you want to
change how something is implemented or hook into your own code, you can do
that. With VirtualResources, you can create REST endpoints that are not backed
in a database, and you are free to add your own Pyramid views wherever you
woud like.

Getting started
---------------
If you haven't already, create a Pyramid application using the `alchemy` scaffold. See [here](http://docs.pylonsproject.org/projects/pyramid//en/latest/tutorials/wiki2/installation.html). Then add `sofa` to your `setup.py` dependency list and run `python setup.py develop`, or, if you aren't using setuptools, run `pip install sofa` and see a doctor at your earliest convenience.

At the core of Sofa is an `api.yaml` file declaring how your API should look. Create it in the root of your project directory (outside of the package directory). Its basic structure resembles the following:

```
resource_modules:
    - packagename.models

resources:
    bananas:
        class: Banana
        attrs:
            - id:
                mutable: false
            - color
            - name
        # Below, we declare the methods that should be enabled in the API.
        # Methods that are not listed are not enabled. Each method can have
        # different settings (more on that later).
        list:
        create:
            required_fields:
                - name
            optional_fields:
                - color
        read:
        update:
        delete:
```

In your `models.py` file (or wherever you have declared your models -- make sure it is listed under `resource_modules` in `api.yaml`), add the following model:

```
from sofa import APIResource
# Ensure Base and probably DBSession exist or have been imported

class Banana(Base, APIResource):
    __tablename__ = 'bananas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(20))
    color = Column(String(20))

    def __init__(self, name, color='yellow'):
        self.name = name
        self.color = color
```

Looks familiar? It should! Sofa tries to work with your existing models without requiring a lot of new stuff.

Now we need to register Sofa with Pyramid. In your Paste ini file (development.ini, production.ini, etc.), add the following line under `[app:main]`:

```
api_config_location =  %(here)s/api.yaml
```

This assumes you saved the API configuration file in the root directory of the project (where you start `pserve` from). If you have saved it as a different name or in a different location, you will need to update this line.

Then, in your root package `__init__.py`, `import sofa`. In the `main` function, after you have configured your `DBSession`, add the following:

```
sofa.configure(sqla_session=DBSession,
               api_config_path=settings['api_config_location'])
```

When you instantiate the Pyramid `Configurator`, pass it `root_factory=sofa.TraversalRoot`:

```
config = Configurator(root_factory=sofa.TraversalRoot, settings=settings)
```

Finally, once `Configurator` is instantiated, add:

```
config.include('sofa')
```

The entire file might look something like this:

```
import logging
import sofa

from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from models import DBSession, Base


def main(global_config, **settings):
    logging.basicConfig(level=logging.DEBUG)
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    sofa.configure(sqla_session=DBSession,
                   api_config_path=settings['api_config_location'])
    config = Configurator(root_factory=sofa.TraversalRoot, settings=settings)
    config.include('sofa')
    config.scan()
    return config.make_wsgi_app()
```

Sofa uses Pyramid's Traversal routing for its API. If you would rather have Sofa operate on its own path prefix (e.g. at "/api/..." instead of "/..."),
or if you would like to use URL dispatch as well, you can use Pyramid's [hybrid routing](http://docs.pylonsproject.org/projects/pyramid//en/latest/narr/hybrid.html#hybrid-applications). If you're fine with Sofa operating on '/' but just want to add some of your own views (e.g. at '/login', because you don't like being RESTful), you can add them as normal and they will override anything that Sofa uses. To have Sofa operate on its own path prefix, pass the `root_factory` argument to a `config.add_route` call instead of the `Configurator` constructor. Concretely:

```
config = Configurator(settings=settings)
...
config.add_route('api', '/api/*traverse', factory=sofa.TraversalRoot)
```

That's it! You now have an extremely basic REST API, well-integrated with your Pyramid application. `pserve` as normal and carry on.

```
$ curl -s -X GET 'http://localhost:6543/' | python -m json.tool
{
    "errorID": "v0-404",
    "message": "You must specify a root resource type (e.g. /bananas). Available resource types are: bananas",
    "statusCode": 404
}

$ curl -s -X GET 'http://localhost:6543/bananas' | python -m json.tool
[]

$ curl -s -X POST 'http://localhost:6543/bananas' | python -m json.tool
{
    "errorID": "bad_name",
    "message": "The name field is mandatory.",
    "statusCode": 400
}

$ curl -s -X POST -F "name=bob" -F "foo=bar" 'http://localhost:6543/bananas' | python -m json.tool
{
    "errorID": "unrecognized_fields",
    "message": "The following key(s) are not recognized fields for this resource: foo. No data has been modified.",
    "statusCode": 400
}

$ curl -s -X POST -F "name=bob" -F "color=brown" 'http://localhost:6543/bananas' | python -m json.tool
{
    "message": "Resource created.",
    "resourceID": 1,
    "statusCode": 201
}

$ curl -s -X GET 'http://localhost:6543/bananas' | python -m json.tool
[
    {
        "active": true,
        "color": "brown",
        "created_at": "2015-07-25T04:16:03Z",
        "deleted_at": null,
        "id": 1,
        "name": "bob",
        "updated_at": "2015-07-25T04:16:03Z"
    }
]

$ curl -s -X GET 'http://localhost:6543/bananas/1' | python -m json.tool
{
    "active": true,
    "color": "brown",
    "created_at": "2015-07-25T04:16:03Z",
    "deleted_at": null,
    "id": 1,
    "name": "bob",
    "updated_at": "2015-07-25T04:16:03Z"
}

$ curl -s -X PUT -F "color=yellow" 'http://localhost:6543/bananas/1' | python -m json.tool
{
    "errorID": "resource_updated",
    "message": "Resource updated.",
    "statusCode": 200
}

$ curl -s -X GET 'http://localhost:6543/bananas/1' | python -m json.tool
{
    "active": true,
    "color": "yellow",
    "created_at": "2015-07-25T04:16:03Z",
    "deleted_at": null,
    "id": 1,
    "name": "bob",
    "updated_at": "2015-07-25T04:17:25Z"
}

$ curl -s -X DELETE 'http://localhost:6543/bananas/1' | python -m json.tool
{
    "errorID": "resource_deleted",
    "message": "Resource deleted.",
    "statusCode": 200
}

$ curl -s -X GET 'http://localhost:6543/bananas' | python -m json.tool
[]
```

How does it handle requests?
----------------------------

### Create

When Sofa gets a "create" request (i.e. a POST request to a collection), it will first check that the request is authorized. If so, it will first check all of the fields that have been sent against the `required_fields` and `optional_fields` lists under `create` in your API config. If required fields are missing, or if unrecognized fields are present, it will return an error. If all is well, it will take those fields and pass them as-is to the resource constructor (`__init__`) by name (so you should ensure that the name of each argument in the constructor matches the name of the attr/field as declared in your API config). It does _not_ pass the values through writer functions before passing them to the constructor; everything is passed as was received in the HTTP request. If you have a password field, hash it in your constructor, because it will be passed in unhashed.

Occasionally, you need to create resources with some extra information that you don't end up storing as an attribute. For example, you might have a Session resource, and you need to pass in the user's password in order to create the Session (for verification purposes), but obviously don't want to store the password in the Session object. For these cases, add an "attribute" to the resource's `attrs` list, add it under `required_fields`, but make the attr both not readable and not mutable. For example:

```
resources:
    sessions:
        class: Session
        attrs:
            - id:
                mutable: false
            - user_id:
                mutable: false
            - username:
                mutable: false
            - password:
                mutable: false
                readable: false
            - expires:
                mutable: false
        create:
            required_fields:
                - username
                - password
        read:
        delete:
```

Even though no `password` attribute actually exists on `Session`, you can use this (with all functionality associated with normal attributes) in Session creation.

### Read

When Sofa gets a "read" request (i.e. a GET request to a resource), it will check that the request is authorized, then fetch the resource from the database (using the resource ID from the URL). It looks up the primary key and uses that when searching for a resource, so you must make your primary key the field that you would like to use to identify resources in URLs. For example, if you want `/users/someusername` to resolve to a user, you must use a username field as the primary key; if you want `/users/924` to resolve, you must use a numerical id field as the primary key.

Once Sofa has retrieved the resource, it attempts to serialize it by calling its `__json__()` method. This method is provided and inherited by `APIResource` so you do not need to implement it, but you may override its functionality if you so desire. (The method takes `self` and `request`, and must return a dictionary, where each key/value can also be serialized to JSON.)

### List

When Sofa gets a "list" request (i.e. a GET request to a collection), it verify authorization and then query the database for all active resources (i.e. those where the `active` attribute on the resource, automatically included by Sofa, indicating whether a resource has not or has been deleted -- see **Conservation of data** below) and return these resources in a list. The JSON serializer will call the `__json__()` method on each individual resource (see **Read** above). List requests can include filters and other parameters -- documentation coming soon.

### Update

An "update" request (i.e. a PUT request to a resource) contains one or more parameters in the request body that the caller is looking to update. (For example, in the "Getting Started" example, we UPDATEd `color=yellow`, but could have included any number of parameters to update in a single request as well.) When Sofa gets such a request, it checks that the caller is authorized to make an update request, then checks that the caller is authorized to access each attribute in question and checks that each attribute is `mutable`. If there are any unknown attributes, it will reject the request without making any changes. Otherwise, if everything looks good, it will call the `writer` function for each attribute, passing it the value from the HTTP request, and then will update the database with the output of the `writer` function.

### Delete

A "delete" reequest (i.e. a DELETE request to a resource) is perhaps the simplest of all. Sofa checks that the caller is authorized to make the request, and then sets the `active` attribute on the resource to `False`, marking it as deleted. (See **Conservation of data** below for explanation.)

Controlling authorization
-------------------------

Sofa allows for fine-grain control over access to resource collections, resources, methods used on resources, and attributes on resources by use of "authorization function."

Whenever a request is made to a collection or resource (see **How does it handle requests?** above), the appropriate authorization function will be called. The function may take no arguments, a `ctx` argument, or both `ctx` and `target` arguments. `ctx` refers to an "Authorization Context," represented as an `AuthContext` object (defined in sofa.structure). This object provides information about the context in which this authorization is occuring. `ctx.http_method`, `ctx.params`, and `ctx.request` (the HTTP method of the request, the GET and POST parameters combined, and the Pyramid request, respectively) are always present in every `AuthContext`. If a user is logged in, `ctx.session`, `ctx.caller_id`, and `ctx.caller_type` will be set as well; if not, they will be `None` (but defined, and thus safe to refer to).

The following is an example of setting authorization functions at various levels:

An authorization function can be set on nearly any scope in the API configuration:

```
resource_modules:
    - packagename.models

resources:
    bananas:
        class: Banana
        attrs:
            - id:
                mutable: false
            - color
            - name:
                auth: |
                    lambda: True
        auth: check_general_auth
        list:
        create:
            required_fields:
                - name
            optional_fields:
                - color
            auth: None
        read:
        update:
        delete:
            auth: |
                lambda ctx, target: ctx.session.user_id == target.id
```

In this example, we set an auth function on `bananas` called `check_general_auth`. This refers to `Banana.check_general_auth`, which must be defined in `Banana`. All attributes and methods will inherit this authorization function unless they have their own authorization function set, overriding the global `bananas` one. If a caller makes a "list" or "read" request, this function will be called.

Note that the `name` attr has its own `auth` function set. This function will be called on every "read" and "list" request to ensure that the caller is allowed to view the contents of that attribute. However, `check_general_auth` will be called to make sure that the caller is allowed to make "list" and "read" requests in the first place. Even if `name`'s auth function returns `True` (which it does, always), if `check_general_auth` returns `False`, Sofa will return a `403` and the user will not be able to view everything (i.e. the authorization on the method is more restrictive than the authorization on the attribute, and dominates). If we were to make the authorization function on `name` always return `False`, then if `check_general_auth` returned `True`, the caller would be returned a dictionary with everything except the `name` attribute (i.e. the request succeeds, but the auth function on `name` prevents it from appearing in the results).

The `delete` method has an auth function that takes both an AuthContext and a target. When an auth function is being used to authorize access to collections, the `target` will be the target resource class (e.g. Banana), and when it is being used to authorize access to resources, it will be the target resource instance. In this case, "delete" is only used on resource instances, so `target` will be the instance subject to deletion. Our lambda authorization function ensures the caller ID is the same as the banana ID, effectively ensuring the only thing that can delete a Banana is itself. (Oh dear.)

Conservation of data
--------------------
Sofa never actually deletes things. If it gets an authorized DELETE request, it will mark the "active" attribute on the resource `False`, and for all intents and purposes, the resource will act deleted. However, it will still be in your database in the event you need to restore it.

Potential upcoming features
---------------------------
* More API client generators
* Documentation generator
