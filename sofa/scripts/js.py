import os
import re
import sys

from sofa.parser import get_resource_info

def snake_to_camel(str):
    return str.split('_')[0] + "".join(x.title() for x in str.split('_')[1:])

def http_js(method, url, authenticated=False, data=False, success=None, error=None):
    if data and isinstance(data, (list, tuple)):
        data = 'data: $.param({%s}),' % ',\n'.join('{0}: {1}'.format(param, snake_to_camel(param))
                                                   for param in data)
    elif data and not isinstance(data, (list, tuple)):
        data = 'data: $.param(data),'
    else:
        data = ''
    if authenticated:
        http_call = \
        """$http({
               method: "%s",
               url: %s,
               %s
               headers: {"Content-Type": "application/x-www-form-urlencoded",
                         "Authorization": "Token " + $cookieStore.get("authToken")}
            })""" % (method, url, data if data else '')
    else:
        http_call = \
        """$http({
               method: "%s",
               url: %s,
               %s
               headers: {"Content-Type": "application/x-www-form-urlencoded"}
            })""" % (method, url, data if data else '')
    if success:
        http_call += ".success({success})".format(success=success)
    if error:
        http_call += ".error({error})".format(error=error)
    http_call += ";"
    return http_call


def function_js(body, name='', *params):
    return "function %s(%s) {%s}" % (name+' ' if name else '',
                                     ', '.join(params),
                                     body)

def factory_function_js(verb, body, *params):
    signature = 'factory.{verb} = function ({params})'\
                    .format(verb=verb,
                            params=', '.join(params))
    return signature + ' {' + body + '};'

def factory_js(main_module_name, name, factories):
    body = \
    """
    %s.factory('%s', function ($http, $cookieStore) {
    "use strict";
    var factory = {}, root = %s.apiURL;
    <linefeed>
    """ % (main_module_name, name, main_module_name)
    for factory in factories:
        body += factory_function_js(factory['verb'],
                                    'return ' +
                                    http_js(method=factory['method'],
                                            url=factory['url'],
                                            authenticated=True if factory['auth'] else False,
                                            data=factory.get('post_params', False)).strip(),
                                    *factory['func_params']) + '<linefeed>'
    body += 'return factory;});'
    return body

def indent(str):
    level = 0;
    out = ''
    str = str.replace('{', '{\n') \
             .replace('}', '\n}') \
             .replace(';', ';\n') \
             .replace('<linefeed>', '<linefeed>\n')
    str = re.sub(r'\)\s+;', ');', str)
    str = re.sub(r'\)\s+\.', ').', str)
    str = re.sub(r'{\s+}', '{}', str)
    for line in str.split('\n'):

        if line.strip().startswith('}'):
            level = level - 1
        if line.strip():
            line = (' ' * 4 * level) + line.strip()
            line = re.sub(r'^\s+<linefeed>', '', line)
            out += line + '\n'
        if line.endswith('{'):
            level = level + 1

    return out

def main(argv=sys.argv):
    if len(argv) != 3:
        cmd = os.path.basename(argv[0])
        print('usage: %s <api_config> <angular_module_name>\n'
              '(example: "%s api.yaml mainModule")' % (cmd, cmd))
        sys.exit(1)
    resources = get_resource_info(argv[1])['api']
    main_module_name = argv[2]
    js_file = ('/**********************************************************\n'
               '*                SOFA ANGULAR API FACTORIES               *\n'
               '* These factories are auto-generated. Do not modify them. *\n'
               '**********************************************************/\n\n')
    for cls, info in resources.iteritems():
        factories = []
        if info['list']:
            verb = 'list'
            method = 'GET'
            url = 'root + "%s"' % info['list']['url'] \
                + '\n + (options ? ("?" + Object.keys(options).map(function(val) {' \
                + '\n             return val+"="+options[val];' \
                + '\n         }).join("&")) : "")'
            factories.append({'verb': verb,
                              'method': method,
                              'url': url,
                              'func_params': ['options'],
                              'auth': info['list']['auth']})
        if info['create']:
            verb = 'create'+cls
            method = 'POST'
            url = 'root + "%s"' % info['create']['url']
            factories.append({'verb': verb,
                              'method': method,
                              'url': url,
                              'func_params': ('data',),
                              'post_params': True,
                              'auth': info['create']['auth']})
        if info['read']:
            verb = 'get'+cls
            method = 'GET'
            url = 'root + "%s"' % info['read']['url']
            url_params = [ segment[1:] for segment in info['read']['url'].split('/')
                           if segment.startswith(':') ]
            for param in url_params:
                url += '.replace(":%s", %s)' % (param, snake_to_camel(param))
            url += '\n + (options ? ("?" + Object.keys(options).map(function(val) {' \
                 + '\n             return val+"="+options[val];' \
                 + '\n         }).join("&")) : "")'
            factories.append({'verb': verb,
                              'method': method,
                              'url': url,
                              'func_params': [snake_to_camel(param) for param in url_params] + ['options'],
                              'auth': info['read']['auth']})
            # Create getter functions for children
            for key, child in info['children'].iteritems():
                info['get_'+key] = {'method': 'GET',
                                    'url': info['read']['url'].split('/', 1)[-1]+'/'+key,
                                    'auth': info['read']['auth']}
        if info['update']:
            verb = 'update'+cls
            method = 'PATCH'
            url = 'root + "%s"' % info['update']['url']
            url_params = [ segment[1:] for segment in info['update']['url'].split('/')
                           if segment.startswith(':') ]
            for param in url_params:
                url += '.replace(":%s", %s)' % (param, snake_to_camel(param))
            factories.append({'verb': verb,
                              'method': method,
                              'url': url,
                              'func_params': [snake_to_camel(param) for param
                                         in url_params]+['data'],
                              'post_params': True,
                              'auth': info['update']['auth']})
        if info['delete']:
            verb = 'delete'+cls
            method = 'DELETE'
            url = 'root + "%s"' % info['delete']['url']
            url_params = [ segment[1:] for segment in info['delete']['url'].split('/')
                           if segment.startswith(':') ]
            for param in url_params:
                url += '.replace(":%s", %s)' % (param, snake_to_camel(param))
            factories.append({'verb': verb,
                              'method': method,
                              'url': url,
                              'func_params': [snake_to_camel(param) for param in url_params],
                              'auth': info['delete']['auth']})
        group_name = info['group_name']
        info.pop('group_name', None)
        info.pop('attrs', None)
        info.pop('children', None)
        info.pop('auth', None)
        info.pop('list')
        info.pop('create')
        info.pop('read')
        info.pop('update')
        info.pop('delete')
        info.pop('root_accessible')
        for action, directives in info.iteritems():
            if directives:
                verb = snake_to_camel(action)
                method = directives['method'].upper()
                url = 'root + "%s/%s"' % (group_name, directives['url'])
                url_params = [ segment[1:] for segment in directives['url'].split('/')
                               if segment.startswith(':') ]
                for param in url_params:
                    url += '.replace(":%s", %s)' % (param, snake_to_camel(param))
                if method in ('POST', 'PUT', 'PATCH') and directives['params'] is not None:
                    post_params = directives['params']
                    func_params = [snake_to_camel(param) for param in url_params] \
                                + [snake_to_camel(param) for param in post_params]
                elif method in ('POST', 'PUT', 'PATCH') and directives is None:
                    post_params = True
                    func_params = [snake_to_camel(param) for param in url_params] + ['data']
                else:
                    post_params = False
                    func_params = [snake_to_camel(param) for param in url_params]
                factories.append({'verb': verb,
                                  'method': method,
                                  'url': url,
                                  'func_params': func_params,
                                  'post_params': post_params,
                                  'auth': directives['auth']})
        js_file += indent(factory_js(main_module_name, cls+'Factory', factories)) + '\n'
    print js_file.strip()

if __name__ == '__main__':
    main()
