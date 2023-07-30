from numbers import Number
from typing import (
    Callable,
    Optional,
    TypedDict,
    Union
)

from packaging import version

from redistricting.core.utils import tr

schemaVersion = version.parse('1.0.1')

class fieldSchema(TypedDict):
    layer: str
    field: str
    expression: bool
    caption: str

class dataFieldSchema(fieldSchema):
    sum: bool
    pctbase: Optional[str]

class dataFieldSchema1_0_0(fieldSchema):
    sum: bool
    pctbase: int

class baseDistSchema(TypedDict):
    district: int
    name: str

class distSchema(baseDistSchema, total=False):
    description: str
    members: int

class splitSchema(TypedDict):
   districts: Union[str,dict[str, Number]]
   splits: int

statsSchema = TypedDict(
    'statsSchema', 
    {
        'cut-edges': dict[int, int],
        'splits': dict[str, list[splitSchema]]
    }
)           

planSchema = TypedDict(
    'planSchema', 
    {
        'id': str,
        'name': str,
        'description': str,
        'total-population': Number,
        'num-districts': int,
        'num-seats': int,
        'deviation': float,

        'pop-layer': str,
        'pop-join-field':str,

        'geo-layer': str,
        'geo-join-field': str,

        'assign-layer': str,
        'geo-id-field': str,
        'geo-id-caption': str,
        'geo-fields': list[fieldSchema],
        'dist-field': str,

        'dist-layer': str,
        'pop-field': str,
        'pop-fields': list[fieldSchema],
        'data-fields': list[dataFieldSchema],

        'districts': list[distSchema],
        'plan-stats': statsSchema
    }
)

planSchema1_0_0 = TypedDict(
    'planSchema', 
    {
        'id': str,
        'name': str,
        'description': str,
        'total-population': Number,
        'num-districts': int,
        'num-seats': int,
        'deviation': float,

        'pop-layer': str,
        'join-field':str,

        'src-layer': str,
        'src-id-field': str,

        'assign-layer': str,
        'geo-id-field': str,
        'geo-id-display': str,
        'geo-fields': list[fieldSchema],
        'dist-field': str,

        'dist-layer': str,
        'pop-field': str,
        'vap-field': Optional[str],
        'cvap-field': Optional[str],
        'data-fields': list[dataFieldSchema1_0_0],

        'districts': list[distSchema],
        'plan-stats': statsSchema
    }
)

def _renameField(data: dict, old_name: str, new_name: str):
    if old_name in data:
        data[new_name] = data[old_name]
        del data[old_name]

def migrateSchema1_0_0_to_1_0_1(data: dict):
    _renameField(data, 'join-field', 'pop-join-field')
    _renameField(data, 'geo-id-display', 'geo-id-caption')
    _renameField(data, 'src-layer', 'geo-layer')
    _renameField(data, 'src-id-field', 'geo-join-field')

    vap = data.get('vap-field')
    if vap:
        if 'pop-fields' not in data:
            data['pop-fields'] = []

        data['pop-fields'].append(
            fieldSchema(
                layer=data['pop-layer'],
                field = vap,
                expression = False,
                caption = tr("VAP")
            )
        )
        del data['vap-field']

    cvap = data.get('cvap-field')
    if cvap:
        if 'pop-fields' not in data:
            data['pop-fields'] = []

        data['pop-fields'].append(
            fieldSchema(
                layer=data['pop-layer'],
                field = cvap,
                expression = False,
                caption = tr("CVAP")
            )
        )
        del data['cvap-field']

    for field in data.get('data-fields', []):
        if field['pctbase'] == 1:
            field['pctbase'] = data['pop-field']
        elif field['pctbase'] == 2:
            field['pctbase'] = vap
        elif field['pctbase'] == 3:
            field['pctbase'] = cvap
        else:
            field['pctbase'] = None

    return data, version.parse('1.0.1')

migrations: dict[version.Version, Callable[[dict],tuple[dict,version.Version]]] = {
    version.parse('1.0.0'): migrateSchema1_0_0_to_1_0_1
}

schemas = {
    version.parse('1.0.0'): planSchema1_0_0,
    schemaVersion: planSchema
}

def checkMigrateSchema(data: dict, v: version.Version):
    if not v in schemas:
        raise ValueError(f"invalid schema version: {str(v)}")
    
    while v < schemaVersion:
        migrate = migrations[v]
        data, v = migrate(data)

    return data
