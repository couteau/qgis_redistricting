# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - redistricting schema management

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
import json
from numbers import Number
from typing import (
    Any,
    Callable,
    Optional,
    TypedDict,
    Union
)

import pandas as pd
from packaging import version
from qgis.core import (
    QgsExpression,
    QgsProject,
    QgsVectorLayer
)

from redistricting.models.columns import MetricsColumns

from ..models import DistrictColumns
from ..models.base.serialization import camel_to_kebab
from ..models.metricslist import (
    MetricLevel,
    metrics_classes
)
from ..utils import (
    makeFieldName,
    spatialite_connect,
    tr
)

schemaVersion = version.parse('1.0.5')


class fieldSchema1_0_0(TypedDict):
    layer: str
    field: str
    expression: bool
    caption: str


class dataFieldSchema1_0_0(fieldSchema1_0_0):
    sum: bool
    pctbase: int


class baseDistSchema1_0_0(TypedDict):
    district: int
    name: str


class distSchema1_0_0(baseDistSchema1_0_0, total=False):
    description: str
    members: int


class splitSchema1_0_0(TypedDict):
    districts: Union[str, dict[str, Number]]
    splits: int


statsSchema1_0_0 = TypedDict(
    'statsSchema1_0_1',
    {
        'cut-edges': dict[int, int],
        'splits': dict[str, list[splitSchema1_0_0]]
    }
)

planSchema1_0_0 = TypedDict(
    'planSchema1_0_0',
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
        'geo-fields': list[fieldSchema1_0_0],
        'dist-field': str,

        'dist-layer': str,
        'pop-field': str,
        'vap-field': Optional[str],
        'cvap-field': Optional[str],
        'data-fields': list[dataFieldSchema1_0_0],

        'districts': list[distSchema1_0_0],
        'plan-stats': statsSchema1_0_0
    }
)


class dataFieldSchema1_0_1(fieldSchema1_0_0):
    sum: bool
    pctbase: Optional[str]


planSchema1_0_1 = TypedDict(
    'planSchema1_0_1',
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
        'geo-fields': list[fieldSchema1_0_0],
        'dist-field': str,

        'dist-layer': str,
        'pop-field': str,
        'pop-fields': list[fieldSchema1_0_0],
        'data-fields': list[dataFieldSchema1_0_1],

        'districts': list[distSchema1_0_0],
        'plan-stats': statsSchema1_0_0
    }
)

planSchema1_0_2 = TypedDict(
    'planSchema1_0_2',
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
        'geo-fields': list[fieldSchema1_0_0],
        'dist-field': str,

        'dist-layer': str,
        'pop-field': str,
        'pop-fields': list[fieldSchema1_0_0],
        'data-fields': list[dataFieldSchema1_0_1],

        'plan-stats': statsSchema1_0_0
    }
)


class splitSchema(TypedDict):
    index: list[tuple[str, int]]
    columns: list[str]
    data: list[list[Union[int, float]]]


statsSchema1_0_4 = TypedDict(
    'statsSchema1_0_4',
    {
        'cut-edges': int,
        'splits': dict[str, splitSchema],
    }
)


class fieldSchema(TypedDict):
    layer: str
    field: str
    caption: str


dataFieldSchema = TypedDict(
    'dataFieldSchema',
    {
        'layer': str,
        'field': str,
        'caption': str,
        'sum-field': bool,
        'pct-base': Optional[str]
    }
)
dataFieldSchema = TypedDict(
    'dataFieldSchema',
    {
        'layer': str,
        'field': str,
        'caption': str,
        'sum-field': bool,
        'pct-base': Optional[str]
    }
)

planSchema1_0_4 = TypedDict(
    'planSchema1_0_4',
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

        'metrics': statsSchema1_0_4
    }
)


class statsSchema(TypedDict):
    metrics: dict[str, Any]


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


def _renameField(data: dict, old_name: str, new_name: str):
    if old_name in data:
        data[new_name] = data[old_name]
        del data[old_name]


def migrateSchema1_0_0_to_1_0_1(data: planSchema1_0_0):
    migrated = planSchema1_0_1(data)
    _renameField(migrated, 'join-field', 'pop-join-field')
    _renameField(migrated, 'geo-id-display', 'geo-id-caption')
    _renameField(migrated, 'src-layer', 'geo-layer')
    _renameField(migrated, 'src-id-field', 'geo-join-field')

    migrated['pop-fields'] = []

    vap = migrated.get('vap-field')
    if vap:
        migrated['pop-fields'].append(
            fieldSchema(
                layer=migrated['pop-layer'],
                field=vap,
                expression=False,
                caption=tr("VAP")
            )
        )
        del migrated['vap-field']

    cvap = migrated.get('cvap-field')
    if cvap:
        migrated['pop-fields'].append(
            fieldSchema(
                layer=migrated['pop-layer'],
                field=cvap,
                expression=False,
                caption=tr("CVAP")
            )
        )
        del migrated['cvap-field']

    for field in migrated.get('data-fields', []):
        if field['pctbase'] == 1:
            field['pctbase'] = migrated['pop-field']
        elif field['pctbase'] == 2:
            field['pctbase'] = vap
        elif field['pctbase'] == 3:
            field['pctbase'] = cvap
        else:
            field['pctbase'] = None

    splits = migrated["plan-stats"].get("splits")
    split_data: dict[str, list] = {}
    if splits:
        for f, s in splits.items():
            split_data[f] = [
                {f: g[0], "districts": {}, "splits": g[1]} for g in s
            ]
    migrated["plan-stats"]["splits"] = split_data

    return migrated, version.parse('1.0.1')


def _updateDistLayer1_0_1_to_1_0_2(data: planSchema1_0_1):
    distLayer: QgsVectorLayer = QgsProject.instance().mapLayer(data.get('dist-layer'))
    if distLayer is None:
        return

    geoPackagePath, _ = distLayer.source().split('|', 1)

    fields = {
        "deviation": "deviation REAL DEFAULT 0",
        "pct_deviation": "pct_deviation REAL DEFAULT 0",
        "description": "description TEXT",
        "pieces": "pieces INT"
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
                sql = "UPDATE districts SET name = ? WHERE district = ?"
                db.executemany(sql, [(f["name"], f["district"]) for f in data["districts"]])
        distLayer.reload()


def migrateSchema1_0_1_to_1_0_2(data: planSchema1_0_1):
    _updateDistLayer1_0_1_to_1_0_2(data)

    plan_splits = {}
    splits = data["plan-stats"].get("splits")
    if splits:
        for f, s in splits.items():
            if len(s) == 0:
                continue
            index = []
            split_data = []
            columns = None
            for g in s:
                geoid = g[f]
                if 'name' in g:
                    name = g['name']
                else:
                    name = None

                if columns is None:
                    columns = [data['pop-field']] + \
                        [makeFieldName(f["field"], f["caption"]) for f in data.get('pop-fields', [])] + \
                        [makeFieldName(f["field"], f["caption"]) for f in data.get('data-fields', [])]
                    if name:
                        columns.append('__name')

                if 'districts' not in g or len(g['districts']) == 0:
                    continue

                for d, p in g['districts'].items():
                    index.append([geoid, int(d)])
                    row = list(p.values())
                    if name:
                        row.append(name)
                    split_data.append(row)

            plan_splits[f] = {"index": index, "columns": columns, "data": split_data}

        del data['plan-stats']['splits']

    data["plan-stats"]["plan-splits"] = plan_splits

    del data["districts"]
    return data, version.parse('1.0.2')


def migrateSchema1_0_2_to_1_0_3(data: planSchema1_0_2):
    distLayer: QgsVectorLayer = QgsProject.instance().mapLayer(data.get('dist-layer'))
    if distLayer is None:
        return data, version.parse('1.0.3')

    geoPackagePath, _ = distLayer.source().split('|', 1)

    if data['pop-field'] != DistrictColumns.POPULATION and distLayer.fields().lookupField(data['pop-field']) != -1:
        with spatialite_connect(geoPackagePath) as db:
            sql = f"ALTER TABLE districts RENAME COLUMN {data['pop-field']} TO {DistrictColumns.POPULATION}"
            db.execute(sql)
        distLayer.reload()

    return data, version.parse('1.0.3')


def migrateSchema1_0_3_to_1_0_4(data: planSchema1_0_2):
    def addKeyField(fld: dict[str, Any]):
        l: QgsVectorLayer = QgsProject.instance().mapLayer(fld.get('layer'))
        if l is None:
            return

        index = QgsExpression.expressionToLayerFieldIndex(fld.get('field'), l)
        if index == -1:
            return

        relations = l.referencingRelations(index)
        if not relations:
            return
        rel = relations[0]
        refi = rel.referencedFields()
        if len(refi) != 1:
            return
        fld['name-field']['key-field'] = l.fields().field(refi[0]).name()

    if 'geo-layer' not in data and 'pop-layer' in data:
        data['geo-layer'] = data['pop-layer']
        del data['pop-layer']

    for field in data.get('geo-fields', []):
        if 'expression' in field:
            del field['expression']
        if 'name-field' in field and 'key-field' not in field['name-field']:
            addKeyField(field)

    for field in data.get('pop-fields', []):
        if 'expression' in field:
            del field['expression']

    for field in data.get('data-fields', []):
        if 'expression' in field:
            del field['expression']
        _renameField(field, 'sum', 'sum-field')
        _renameField(field, 'pctbase', 'pct-base')

    splits: dict[str, dict] = data['plan-stats'].pop('plan-splits', {})
    for k, v in splits.items():
        v = json.loads(
            pd.DataFrame(
                v['data'],
                columns=v['columns'],
                index=pd.MultiIndex.from_tuples(v['index'], names=[k, data['dist-field']])
            )
            .to_json(orient='table')
        )
        split = {'field': k, 'data': v}
        splits[k] = split
    data['plan-stats']['splits'] = splits
    _renameField(data, 'plan-stats', 'metrics')

    return data, version.parse('1.0.4')


def migrateSchema1_0_4_to_1_0_5(data: planSchema1_0_4):
    metrics: dict[str, Any] = {
        camel_to_kebab(n): None for n, m in metrics_classes.items()
        if m.level() != MetricLevel.DISTRICT and m.serialize()
    }
    metrics['total-population'] = data['total-population']

    distLayer: QgsVectorLayer = QgsProject.instance().mapLayer(data.get('dist-layer'))
    if distLayer is not None:
        geoPackagePath, _ = distLayer.source().split('|', 1)
        with spatialite_connect(geoPackagePath) as db:
            ideal = data['total-population'] / data.get('num-seats', data['num-districts'])

            cur = db.execute(
                f"SELECT min(({DistrictColumns.POPULATION}-members*{ideal})/(members*{ideal})) AS min_deviation, "
                f"max(({DistrictColumns.POPULATION}-members*{ideal})/(members*{ideal})) AS max_deviation, "
                f"min({MetricsColumns.POLSBYPOPPER}) AS minpolsbypopper, "
                f"max({MetricsColumns.POLSBYPOPPER}) AS maxpolsbypopper, "
                f"avg({MetricsColumns.POLSBYPOPPER}) AS meanpolsbypopper, "
                f"min({MetricsColumns.REOCK}) AS minreock, "
                f"max({MetricsColumns.REOCK}) AS maxreock, "
                f"avg({MetricsColumns.REOCK}) AS meanreock, "
                f"min({MetricsColumns.CONVEXHULL}) AS minconvexhull, "
                f"max({MetricsColumns.CONVEXHULL}) AS maxconvexhull, "
                f"avg({MetricsColumns.CONVEXHULL}) AS meanconvexhull "
                "FROM districts"
            )
            mindev, maxdev, \
                metrics['min-polsbypopper'], metrics['max-polsbypopper'], metrics['mean-polsbypopper'], \
                metrics['min-reock'], metrics['max-reock'], metrics['mean-reock'], \
                metrics['min-convexhull'], metrics['max-convexhull'], metrics['mean-convexhull'] \
                = cur.fetchone()
            metrics['plan-deviation'] = [mindev, maxdev]

            cur = db.execute("SELECT count(*) FROM districts HAVING NumGeometries(geometry) > 1")
            metrics['contiguity'] = not bool(cur.fetchall())

            cur = db.execute(
                f"SELECT count(*) FROM assignments WHERE {data['dist-field']} = 0 OR {data['dist-field']} IS NULL")
            metrics['complete'] = cur.fetchone()[0] == 0

    metrics['cut-edges'] = data['metrics'].pop('cut-edges', 0)
    metrics['splits'] = data['metrics'].pop('splits', {})
    data['metrics']['metrics'] = metrics

    return data, version.parse('1.0.5')


migrations: dict[version.Version, Callable[[dict], tuple[dict, version.Version]]] = {
    version.parse('1.0.0'): migrateSchema1_0_0_to_1_0_1,
    version.parse('1.0.1'): migrateSchema1_0_1_to_1_0_2,
    version.parse('1.0.2'): migrateSchema1_0_2_to_1_0_3,
    version.parse('1.0.3'): migrateSchema1_0_3_to_1_0_4,
    version.parse('1.0.4'): migrateSchema1_0_4_to_1_0_5,
}

schemas = {
    version.parse('1.0.0'): planSchema1_0_0,
    version.parse('1.0.1'): planSchema1_0_1,
    version.parse('1.0.2'): planSchema1_0_2,
    version.parse('1.0.3'): planSchema1_0_2,
    version.parse('1.0.4'): planSchema1_0_4,
    schemaVersion: planSchema
}


def needsMigration(v: version.Version):
    return v < schemaVersion


def checkMigrateSchema(data: dict, v: version.Version):
    if not v in schemas:
        raise ValueError(f"invalid schema version: {str(v)}")

    while v < schemaVersion:
        migrate = migrations[v]
        data, v = migrate(data)

    return data
