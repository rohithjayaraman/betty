from collections import defaultdict
from typing import List, Tuple, Callable, Set, Type

from betty.ancestry import Ancestry, Place, File, IdentifiableEvent, IdentifiableSource, IdentifiableCitation
from betty.event import Event
from betty.graph import Graph, tsort
from betty.parse import PostParseEvent
from betty.plugin import Plugin
from betty.plugins.anonymizer import Anonymizer


def clean(ancestry: Ancestry) -> None:
    _clean_people(ancestry)
    _clean_events(ancestry)
    _clean_places(ancestry)
    _clean_files(ancestry)
    _clean_citations(ancestry)
    _clean_sources(ancestry)


def _clean_events(ancestry: Ancestry) -> None:
    for event in list(ancestry.events.values()):
        _clean_event(ancestry, event)


def _clean_event(ancestry: Ancestry, event: IdentifiableEvent) -> None:
    if len(event.presences) > 0:
        return

    del event.place
    del event.citations
    del event.files
    del ancestry.events[event.id]


def _clean_places(ancestry: Ancestry) -> None:
    places = list(ancestry.places.values())

    def _extend_place_graph(graph: Graph, enclosing_place: Place) -> None:
        enclosed_places = enclosing_place.encloses
        # Ensure each place appears in the graph, even if they're anonymous.
        graph.setdefault(enclosing_place, set())
        for enclosed_place in enclosed_places:
            seen_enclosed_place = enclosed_place in graph
            graph[enclosed_place].add(enclosing_place)
            if not seen_enclosed_place:
                _extend_place_graph(graph, enclosed_place)

    places_graph = defaultdict(set)
    for place in places:
        _extend_place_graph(places_graph, place)

    for place in tsort(places_graph):
        _clean_place(ancestry, place)


def _clean_place(ancestry: Ancestry, place: Place) -> None:
    if len(place.events) > 0:
        return

    if len(place.encloses) > 0:
        return

    del place.enclosed_by
    del ancestry.places[place.id]


def _clean_people(ancestry: Ancestry) -> None:
    for person in list(ancestry.people.values()):
        if person.private and len(person.children) == 0:
            del ancestry.people[person.id]


def _clean_files(ancestry: Ancestry) -> None:
    for file in list(ancestry.files.values()):
        _clean_file(ancestry, file)


def _clean_file(ancestry: Ancestry, file: File) -> None:
    if len(file.resources) > 0:
        return

    del ancestry.files[file.id]


def _clean_sources(ancestry: Ancestry) -> None:
    for source in list(ancestry.sources.values()):
        _clean_source(ancestry, source)


def _clean_source(ancestry: Ancestry, source: IdentifiableSource) -> None:
    if len(source.citations) > 0:
        return

    if source.contained_by is not None:
        return

    if len(source.contains) > 0:
        return

    if len(source.files) > 0:
        return

    del ancestry.sources[source.id]


def _clean_citations(ancestry: Ancestry) -> None:
    for citation in list(ancestry.citations.values()):
        _clean_citation(ancestry, citation)


def _clean_citation(ancestry: Ancestry, citation: IdentifiableCitation) -> None:
    if len(citation.facts) > 0:
        return

    if len(citation.files) > 0:
        return

    del citation.source
    del ancestry.citations[citation.id]


class Cleaner(Plugin):
    @classmethod
    def comes_after(cls) -> Set[Type[Plugin]]:
        return {Anonymizer}

    def subscribes_to(self) -> List[Tuple[Type[Event], Callable]]:
        return [
            (PostParseEvent, lambda event: clean(event.ancestry)),
        ]
