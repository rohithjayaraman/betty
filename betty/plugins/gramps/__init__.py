import gzip
import re
import tarfile
from os import mkdir
from os.path import join, dirname
from typing import Tuple, Optional, Callable, List, Dict

from geopy import Point
from lxml import etree
from lxml.etree import XMLParser, Element

from betty.ancestry import Document, Event, Place, Person, Ancestry, Date, Note, File
from betty.parse import ParseEvent
from betty.plugin import Plugin
from betty.site import Site


class _IntermediateAncestry:
    def __init__(self):
        self.notes = {}
        self.documents = {}
        self.places = {}
        self.events = {}
        self.people = {}

    def populate(self, ancestry: Ancestry):
        ancestry.documents = {
            document.id: document for document in self.documents.values()}
        ancestry.people = {
            person.id: person for person in self.people.values()}
        ancestry.places = {place.id: place for place in self.places.values()}
        ancestry.events = {event.id: event for event in self.events.values()}


class _IntermediatePlace:
    def __init__(self, place: Place, enclosed_by_handle: Optional[str]):
        self.place = place
        self.enclosed_by_handle = enclosed_by_handle


_NS = {
    'ns': 'http://gramps-project.org/xml/1.7.1/',
}


def _xpath(element, selector: str) -> []:
    return element.xpath(selector, namespaces=_NS)


def _xpath1(element, selector: str) -> []:
    elements = element.xpath(selector, namespaces=_NS)
    if elements:
        return elements[0]
    return None


def extract_xml_file(gramps_file_path: str, working_directory_path: str) -> str:
    gramps_working_directory_path = join(working_directory_path, Gramps.name())
    mkdir(gramps_working_directory_path)
    ungzipped_outer_file = gzip.open(gramps_file_path)
    xml_file_path = join(gramps_working_directory_path, 'data.xml')
    with open(xml_file_path, 'wb') as xml_file:
        try:
            tarfile.open(fileobj=ungzipped_outer_file).extractall(
                gramps_working_directory_path)
            gramps_file_path = join(
                gramps_working_directory_path, 'data.gramps')
            xml_file.write(gzip.open(gramps_file_path).read())
        except tarfile.ReadError:
            xml_file.write(ungzipped_outer_file.read())
    return xml_file_path


def parse_xml_file(ancestry: Ancestry, file_path) -> None:
    parser = XMLParser()
    tree = etree.parse(file_path, parser)
    database = tree.getroot()
    intermediate_ancestry = _IntermediateAncestry()
    _parse_notes(intermediate_ancestry, database)
    _parse_documents(intermediate_ancestry, database, file_path)
    _parse_places(intermediate_ancestry, database)
    _parse_events(intermediate_ancestry, database)
    _parse_people(intermediate_ancestry, database)
    _parse_families(intermediate_ancestry, database)
    intermediate_ancestry.populate(ancestry)


_DATE_PATTERN = re.compile(r'.{4}-.{2}-.{2}')
_DATE_PART_PATTERN = re.compile(r'\d+')


def _parse_date(element: Element) -> Optional[Date]:
    dateval = str(_xpath1(element, './ns:dateval/@val'))
    if _DATE_PATTERN.fullmatch(dateval):
        dateval_parts = dateval.split('-')
        date_parts = [int(val) if _DATE_PART_PATTERN.fullmatch(val) else None for val in dateval_parts] + \
                     [None] * (3 - len(dateval_parts))
        return Date(*date_parts)
    return None


def _parse_notes(ancestry: _IntermediateAncestry, database: Element):
    for element in _xpath(database, './ns:notes/ns:note'):
        _parse_note(ancestry, element)


def _parse_note(ancestry: _IntermediateAncestry, element: Element):
    handle = _xpath1(element, './@handle')
    text = _xpath1(element, './ns:text/text()')
    ancestry.notes[handle] = Note(text)


def _parse_documents(ancestry: _IntermediateAncestry, database: Element, gramps_file_path: str):
    for element in _xpath(database, './ns:objects/ns:object'):
        _parse_document(ancestry, element, gramps_file_path)


def _parse_document(ancestry: _IntermediateAncestry, element: Element, gramps_file_path):
    handle = _xpath1(element, './@handle')
    entity_id = _xpath1(element, './@id')
    file_element = _xpath1(element, './ns:file')
    file_path = join(dirname(gramps_file_path),
                     _xpath1(file_element, './@src'))
    file = File(file_path)
    file.type = _xpath1(file_element, './@mime')
    note_handles = _xpath(element, './ns:noteref/@hlink')
    document = Document(entity_id, file)
    description = _xpath1(file_element, './@description')
    if description:
        document.description = description
    for note_handle in note_handles:
        document.notes.append(ancestry.notes[note_handle])
    ancestry.documents[handle] = document


def _parse_people(ancestry: _IntermediateAncestry, database: Element):
    for element in database.xpath('.//*[local-name()="person"]'):
        _parse_person(ancestry, element)


def _parse_person(ancestry: _IntermediateAncestry, element: Element):
    handle = _xpath1(element, './@handle')
    properties = {
        'individual_name': _xpath1(element, './ns:name[@type="Birth Name"]/ns:first').text,
        'family_name': _xpath1(element, './ns:name[@type="Birth Name"]/ns:surname').text,
    }
    event_handles = _xpath(element, './ns:eventref/@hlink')
    person = Person(_xpath1(element, './@id'), **properties)
    for event_handle in event_handles:
        person.events.add(ancestry.events[event_handle])
    if str(_xpath1(element, './@priv')) == '1':
        person.private = True

    ancestry.people[handle] = person


def _parse_families(ancestry: _IntermediateAncestry, database: Element):
    for element in database.xpath('.//*[local-name()="family"]'):
        _parse_family(ancestry, element)


def _parse_family(ancestry: _IntermediateAncestry, element: Element):
    parents = set()

    # Parse events.
    event_handles = _xpath(element, './ns:eventref/@hlink')
    events = [ancestry.events[event_handle] for event_handle in event_handles]

    # Parse the father.
    father_handle = _xpath1(element, './ns:father/@hlink')
    if father_handle:
        father = ancestry.people[father_handle]
        for event in events:
            father.events.add(event)
        parents.add(father)

    # Parse the mother.
    mother_handle = _xpath1(element, './ns:mother/@hlink')
    if mother_handle:
        mother = ancestry.people[mother_handle]
        for event in events:
            mother.events.add(event)
        parents.add(mother)

    # Parse the children.
    child_handles = _xpath(element, './ns:childref/@hlink')
    for child_handle in child_handles:
        child = ancestry.people[child_handle]
        for parent in parents:
            parent.children.add(child)


def _parse_places(ancestry: _IntermediateAncestry, database: Element):
    intermediate_places = {handle: intermediate_place for handle, intermediate_place in
                           [_parse_place(element) for element in database.xpath('.//*[local-name()="placeobj"]')]}
    for intermediate_place in intermediate_places.values():
        if intermediate_place.enclosed_by_handle is not None:
            intermediate_place.place.enclosed_by = intermediate_places[
                intermediate_place.enclosed_by_handle].place
    ancestry.places = {handle: intermediate_place.place for handle, intermediate_place in
                       intermediate_places.items()}


def _parse_place(element: Element) -> Tuple[str, _IntermediatePlace]:
    handle = _xpath1(element, './@handle')
    properties = {
        'name': _xpath1(element, './ns:pname/@value')
    }
    place = Place(_xpath1(element, './@id'), **properties)

    coordinates = _parse_coordinates(element)
    if coordinates:
        place.coordinates = coordinates

    # Set the first place reference as the place that encloses this place.
    enclosed_by_handle = _xpath1(element, './ns:placeref/@hlink')

    return handle, _IntermediatePlace(place, enclosed_by_handle)


def _parse_coordinates(element: Element) -> Optional[Point]:
    coord_element = _xpath1(element, './ns:coord')

    if coord_element is None:
        return None

    latitudeval = _xpath1(coord_element, './@lat')
    longitudeval = _xpath1(coord_element, './@long')

    try:
        return Point(latitudeval, longitudeval)
    except BaseException:
        # We could not parse/validate the Gramps coordinates, because they are too freeform.
        pass
    return None


def _parse_events(ancestry: _IntermediateAncestry, database: Element):
    for element in database.xpath('.//*[local-name()="event"]'):
        _parse_event(ancestry, element)


_EVENT_TYPE_MAP = {
    'Birth': Event.Type.BIRTH,
    'Death': Event.Type.DEATH,
    'Burial': Event.Type.BURIAL,
    'Marriage': Event.Type.MARRIAGE,
}


def _parse_event(ancestry: _IntermediateAncestry, element: Element):
    handle = _xpath1(element, './@handle')
    gramps_type = _xpath1(element, './ns:type')

    event = Event(_xpath1(element, './@id'), _EVENT_TYPE_MAP[gramps_type.text])

    event.date = _parse_date(element)

    # Parse the event place.
    place_handle = _xpath1(element, './ns:place/@hlink')
    if place_handle:
        event.place = ancestry.places[place_handle]

    # Parse the documents.
    document_handles = _xpath(element, './ns:objref/@hlink')
    for document_handle in document_handles:
        event.documents.add(ancestry.documents[document_handle])

    ancestry.events[handle] = event


class Gramps(Plugin):
    def __init__(self, gramps_file_path: str, working_directory_path: str):
        self._gramps_file_path = gramps_file_path
        self._working_directory_path = working_directory_path

    @classmethod
    def from_configuration_dict(cls, site: Site, configuration: Dict):
        return cls(configuration['file'], site.working_directory_path)

    def subscribes_to(self) -> List[Tuple[str, Callable]]:
        return [
            (ParseEvent, self._parse),
        ]

    def _parse(self, event: ParseEvent) -> None:
        xml_file_path = extract_xml_file(
            self._gramps_file_path, self._working_directory_path)
        parse_xml_file(event.ancestry, xml_file_path)