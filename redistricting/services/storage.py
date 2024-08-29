# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - save/load plans to/from the project file 

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
from typing import (
    Iterable,
    List
)
from uuid import UUID

from packaging import version
from qgis.core import (
    QgsProject,
    QgsReadWriteContext
)
from qgis.PyQt.QtXml import QDomDocument

from ..models import (
    DistrictColumns,
    RdsPlan,
    StatsColumns,
    deserialize,
    serialize
)
from .DistrictIO import (
    DistrictReader,
    DistrictWriter
)
from .schema import (
    checkMigrateSchema,
    schemaVersion
)


class ProjectStorage:
    def __init__(self, project: QgsProject, doc: QDomDocument, context: QgsReadWriteContext = None):
        self._project = project
        self._doc = doc
        self._context = context
        self._version = self.getVersion() or schemaVersion

    def migrate(self):
        """Migrate plugin node in project file to new schema"""
        if self._version < schemaVersion:
            l, success = self._project.readListEntry('redistricting', 'redistricting-plans', [])
            if not success:
                return

            for i, d in enumerate(l):
                data = json.loads(d)
                l[i] = json.dumps(checkMigrateSchema(data, self._version))
            self._project.writeEntry('redistricting', 'redistricting-plans', l)

        self._version = schemaVersion

    def getVersion(self):
        v, success = self._project.readEntry('redistricting', 'schema-version', None)
        if not success or v is None:
            return version.parse('1.0.0')

        return version.parse(v)

    def setVersion(self):
        self._project.writeEntry('redistricting', 'schema-version', str(schemaVersion))

    def readDistricts(self, plan: RdsPlan):
        if plan.distLayer is None:
            return

        columns = [plan.distField, DistrictColumns.NAME,
                   DistrictColumns.MEMBERS, DistrictColumns.POPULATION,
                   DistrictColumns.DEVIATION, DistrictColumns.PCT_DEVIATION,
                   "description"]
        for f in plan.popFields:
            columns.append(f.fieldName)
        for f in plan.dataFields:
            if f.sumField:
                columns.append(f.fieldName)
            if f.pctBase:
                columns.append(f'pct_{f.fieldName}')
        columns.extend(StatsColumns)

        districtReader = DistrictReader(plan.distLayer, plan.distField, plan.popField, columns)
        districtReader.loadDistricts(plan)

    def writeDistricts(self, plan: RdsPlan):
        columns = [plan.distField, DistrictColumns.NAME,
                   DistrictColumns.MEMBERS, DistrictColumns.POPULATION,
                   DistrictColumns.DEVIATION, DistrictColumns.PCT_DEVIATION,
                   "description"]
        for f in plan.popFields:
            columns.append(f.fieldName)
        for f in plan.dataFields:
            columns.append(f.fieldName)
        columns.extend([s for s in StatsColumns])
        if plan.distLayer:
            writer = DistrictWriter(plan.distLayer, plan.distField, plan.popField, columns)
            writer.writeToLayer(plan.districts)

    def writeRedistrictingPlans(self, plans: Iterable[RdsPlan]):
        l: List[str] = []
        for p in plans:
            data = serialize(p)
            jsonPlan = json.dumps(data)
            l.append(jsonPlan)
            self.writeDistricts(p)
        self._project.writeEntry('redistricting', 'redistricting-plans', l)
        self.setVersion()

    def readRedistrictingPlans(self) -> List[RdsPlan]:
        plans = []
        self.migrate()
        l, success = self._project.readListEntry('redistricting', 'redistricting-plans', [])
        if success:
            for p in l:
                planJson = json.loads(p)

                if 'geo-layer' not in planJson and 'pop-layer' in planJson:
                    planJson['geo-layer'] = planJson['pop-layer']
                    del planJson['pop-layer']

                plan = deserialize(RdsPlan, planJson, parent=self._project)
                self.readDistricts(plan)
                if plan is not None:
                    plans.append(plan)
        return plans

    def readActivePlan(self):
        self.migrate()
        uuid, found = self._project.readEntry('redistricting', 'active-plan', None)
        if found:
            try:
                return UUID(uuid)
            except ValueError:
                # ignore malformed uuids
                pass
        return None

    def writeActivePlan(self, plan: RdsPlan):
        if plan is not None:
            self._project.writeEntry('redistricting', 'active-plan', str(plan.id))
        else:
            self._project.removeEntry('redistricting', 'active-plan')
        self.setVersion()
