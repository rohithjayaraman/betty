from typing import Dict

from betty.site import Site
from betty.url import StaticPathUrlGenerator


class _Resource:
    def __init__(self, name: str, collection_endpoint_summary: str, collection_response_description: str,
                 single_endpoint_summary: str, single_response_description):
        self.name = name
        self.collection_endpoint_summary = collection_endpoint_summary
        self.collection_response_description = collection_response_description
        self.single_endpoint_summary = single_endpoint_summary
        self.single_response_description = single_response_description


def _get_resources():
    return [
        _Resource('file', _('Retrieve the collection of files.'), _('The collection of files.'), _('Retrieve a single file.'), _('The file.')),
        _Resource('person', _('Retrieve the collection of people.'), _('The collection of people.'), _('Retrieve a single person.'), _('The person.')),
        _Resource('place', _('Retrieve the collection of places.'), _('The collection of places.'), _('Retrieve a single place.'), _('The place.')),
        _Resource('event', _('Retrieve the collection of events.'), _('The collection of events.'), _('Retrieve a single event.'), _('The event.')),
        _Resource('citation', _('Retrieve the collection of citations.'), _('The collection of citations.'), _('Retrieve a single citation.'), _('The citation.')),
        _Resource('source', _('Retrieve the collection of sources.'), _('The collection of sources.'), _('Retrieve a single source.'), _('The filesource.')),
    ]


def build_specification(site: Site) -> Dict:
    url_generator = StaticPathUrlGenerator(site.configuration)
    specification = {
        'openapi': '3.0.0',
        'servers': [
            {
                'url': url_generator.generate('/', absolute=True),
            }
        ],
        'info': {
            'title': 'Betty',
            'version': 'dev'
        },
        'paths': {},
        'components': {
            'responses': {
                '401': {
                    'description': 'Unauthorized',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/betty/error',
                            },
                        },
                    },
                },
                '403': {
                    'description': 'Forbidden',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/betty/error',
                            },
                        },
                    },
                },
                '404': {
                    'description': 'Not found',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/betty/error',
                            },
                        },
                    },
                },
            },
            'parameters': {
                'id': {
                    'name': 'id',
                    'in': 'path',
                    'required': True,
                    'description': 'The ID for the resource to retrieve.',
                    'schema': {
                        'type': 'string',
                    },
                },
            },
            'headers': {
                'Content-Language': {
                    'description': 'An HTTP [Content-Language](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Language) header.',
                    'schema': {
                        'type': 'string',
                    },
                    'example': site.configuration.default_locale,
                },
            },
            'schemas': {
                'betty': {
                    '$ref': url_generator.generate('/schema.json#/definitions'),
                },
            },
        },
    }
    for resource in _get_resources():
        if site.configuration.content_negotiation:
            collection_path = '/%s/' % resource.name
            single_path = '/%s/{id}/' % resource.name
        else:
            collection_path = '/{locale}/%s/index.json' % resource.name
            single_path = '/{locale}/%s/{id}/index.json' % resource.name
        specification['paths'].update({
            collection_path: {
                'get': {
                    'summary': resource.collection_endpoint_summary,
                    'responses': {
                        '200': {
                            'description': resource.collection_response_description,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        '$ref': '#/components/schemas/betty/%sCollection' % resource.name,
                                    },
                                },
                            },
                        },
                    },
                },
            },
            single_path: {
                'get': {
                    'summary': resource.single_endpoint_summary,
                    'responses': {
                        '200': {
                            'description': resource.single_response_description,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        '$ref': '#/components/schemas/betty/%s' % resource.name,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        })
    if site.configuration.content_negotiation:
        specification['components']['parameters']['Accept-Language'] = {
            'name': 'Accept-Language',
            'in': 'header',
            'description': 'An HTTP [Accept-Language](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language) header.',
            'schema': {
                'type': 'string'
            },
            'example': site.configuration.locales[site.configuration.default_locale].alias
        }
    specification['components']['schemas']['html'] = {
        'type': 'string',
        'description': 'An HTML5 document.'
    }
    responses = list(specification['components']['responses'].values())
    for path in specification['paths']:
        specification['paths'][path]['get']['responses'].update({
            '401': {
                '$ref': '#/components/responses/401',
            },
            '403': {
                '$ref': '#/components/responses/403',
            },
            '404': {
                '$ref': '#/components/responses/404',
            },
        })
        if site.configuration.content_negotiation:
            specification['paths'][path]['parameters'] = [
                {
                    '$ref': '#/components/parameters/Accept-Language',
                },
            ]
        else:
            specification['paths'][path]['parameters'] = [
                {
                    '$ref': '#/components/parameters/locale',
                },
            ]
        responses.append(specification['paths'][path]['get']['responses']['200'])
    for response in responses:
        response['content']['text/html'] = {
            'schema': {
                '$ref': '#/components/schemas/html'
            }
        }
        if 'headers' not in response:
            response['headers'] = {}
        response['headers']['Content-Language'] = {
            '$ref': '#/components/headers/Content-Language',
        }
    else:
        specification['components']['parameters']['locale'] = {
            'name': 'locale',
            'in': 'path',
            'required': True,
            'description': 'A locale name.',
            'schema': {
                'type': 'string',
                'enum': list(site.configuration.locales.keys())
            },
            'example': site.configuration.locales[site.configuration.default_locale].alias
        }

    return specification
