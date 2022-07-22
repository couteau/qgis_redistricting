"""Constants and default values for QGIS redistricting plugin"""
import re
from .Utils import tr

POP_FIELDS = ['pop_total', 'p0010001']
VAP_FIELDS = ['vap_total', 'p0030001']
CVAP_FIELDS = ['cvap_total', re.compile(r'^cvap_(?:\d{4}_)total$')]

GEOID_FIELDS = ['geoid20', 'geoid30', 'geoid10', 'geoid', 'block', 'block_id']

GEOID_LABELS = [
    tr('Block'),
    tr('Block Group'),
    tr('Tract'),
    tr('Precinct/VTD'),
    tr('County/Parish'),
]
