from typing import Any, Callable

from betty.ancestry import Person, Citation, Source, File, Place, Event
from betty.config import Configuration


class UrlGenerator:
    def __init__(self, configuration: Configuration):
        self._configuration = configuration

    def generate(self, resource: Any, absolute: bool = False) -> str:
        _GENERATORS = {
            str: self._generate_for_path,
            Person: self._generator_for_identifiable('person/%s/'),
            Event: self._generator_for_identifiable('event/%s/'),
            Place: self._generator_for_identifiable('place/%s/'),
            File: self._generator_for_identifiable('file/%s/'),
            Source: self._generator_for_identifiable('source/%s/'),
            Citation: self._generator_for_identifiable('citation/%s/'),
        }
        generator = _GENERATORS[type(resource)]
        return generator(resource, absolute)

    def _generator_for_identifiable(self, pattern: str) -> Callable:
        return lambda identifiable, absolute: self._generate_for_path(pattern % identifiable.id, absolute)

    def _generate_for_path(self, path: str, absolute=False):
        url = self._configuration.base_url if absolute else ''
        url += self._configuration.root_path
        url += path.lstrip('/')
        if not self._configuration.clean_urls and path.endswith('/'):
            url += 'index.html'
        return url
