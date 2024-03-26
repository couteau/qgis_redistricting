from numbers import Number
from typing import (
    Callable,
    Optional,
    TypedDict,
    Union
)

from packaging import version
from qgis.core import (
    QgsProject,
    QgsVectorLayer
)

from ..utils import (
    spatialite_connect,
    tr
)

schemaVersion = version.parse('1.0.2')


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


class splitSchema(TypedDict):
    index: list[tuple[str, int]]
    columns: list[str]
    data: list[list[Union[int, float]]]


statsSchema = TypedDict(
    'statsSchema',
    {
        'cut-edges': int,
        'plan-splits': dict[str, splitSchema],
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
        'pop-join-field': str,

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

        'plan-stats': statsSchema
    }
)


class baseDistSchema1_0_1(TypedDict):
    district: int
    name: str


class distSchema1_0_1(baseDistSchema1_0_1, total=False):
    description: str
    members: int


class splitSchema1_0_1(TypedDict):
    districts: Union[str, dict[str, Number]]
    splits: int


statsSchema1_0_1 = TypedDict(
    'statsSchema',
    {
        'cut-edges': dict[int, int],
        'splits': dict[str, list[splitSchema1_0_1]]
    }
)

planSchema1_0_1 = TypedDict(
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
        'pop-join-field': str,

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

        'districts': list[distSchema1_0_1],
        'plan-stats': statsSchema1_0_1
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
        'join-field': str,

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

        'districts': list[distSchema1_0_1],
        'plan-stats': statsSchema1_0_1
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
                field=vap,
                expression=False,
                caption=tr("VAP")
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
                field=cvap,
                expression=False,
                caption=tr("CVAP")
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


def _updateDistLayer(data: dict):
    distLayer: QgsVectorLayer = QgsProject.instance().mapLayer(data.get('dist-layer'))
    if distLayer is None:
        return

    geoPackagePath, _ = distLayer.source().split('|', 1)

    fields = {
        "deviation": "deviation REAL DEFAULT 0",
        "pct_deviation": "pct_deviation REAL DEFAULT 0",
        "description": "description TEXT",
    }
    update_fields = []
    for f in fields:
        if distLayer.fields().lookupField(f) == -1:
            update_fields.append(f)
    if update_fields:
        with spatialite_connect(geoPackagePath) as db:
            sql = ";".join(f"ALTER TABLE districts ADD COLUMN {fields[f]}" for f in update_fields)
            db.executescript(sql)

            if "description" in update_fields:
                sql = "UPDATE districts SET name = ?, description = ? WHERE district = ?"
                db.executemany(sql, [(f["name"], f["description"], f["district"]) for f in data["districts"]])
            else:
                sql = "UPDATE districts SET name = ?, WHERE district = ?"
                db.executemany(sql, [(f["name"], f["district"]) for f in data["districts"]])


def migrateSchema1_0_1_to_1_0_2(data: dict):
    _updateDistLayer(data)

    splits = data["plan-stats"]["splits"]
    plan_splits = {}
    for f, s in splits.items():
        if len(s) == 0:
            continue
        index = []
        split_data = []
        columns = None
        for g in s:
            if 'districts' not in g or len(g['districts']) == 0:
                continue
            geoid = g[f]
            if 'name' in g:
                name = g['name']
            else:
                name = None
            for d, p in g['districts'].items():
                if columns is None:
                    columns = list(p.keys())
                    if name:
                        columns.append('__name')
                index.append([geoid, int(d)])
                row = list(p.values())
                if name:
                    row.append(name)
                split_data.append(row)

        plan_splits[f] = {"index": index, "columns": columns, "data": split_data}

    data["plan-stats"]["plan-splits"] = plan_splits

    del data["districts"]
    return data, version.parse('1.0.2')


migrations: dict[version.Version, Callable[[dict], tuple[dict, version.Version]]] = {
    version.parse('1.0.0'): migrateSchema1_0_0_to_1_0_1,
    version.parse('1.0.1'): migrateSchema1_0_1_to_1_0_2
}

schemas = {
    version.parse('1.0.0'): planSchema1_0_0,
    version.parse('1.0.1'): planSchema1_0_1,
    schemaVersion: planSchema
}


def checkMigrateSchema(data: dict, v: version.Version):
    if not v in schemas:
        raise ValueError(f"invalid schema version: {str(v)}")

    while v < schemaVersion:
        migrate = migrations[v]
        data, v = migrate(data)

    return data
