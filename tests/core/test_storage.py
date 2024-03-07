"""QGIS Redistricting Plugin - unit tests for Storage class

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

import pytest
from pytestqt.plugin import QtBot
from qgis.core import QgsProject
from qgis.PyQt.QtXml import QDomDocument

from redistricting.core.Plan import RedistrictingPlan
from redistricting.core.storage import ProjectStorage


class TestStorage:
    @pytest.fixture
    def storage(self, datadir, qtbot: QtBot) -> ProjectStorage:
        def check_params(d: QDomDocument):
            nonlocal doc
            doc.setContent(d.toString())
            return True

        project = QgsProject.instance()
        doc = QDomDocument()
        with qtbot.waitSignal(project.readProject, check_params_cb=check_params):
            project.read(str((datadir / 'test_project.qgs').resolve()))
        return ProjectStorage(project, doc)

    @pytest.fixture
    def empty_storage(self) -> ProjectStorage:
        return ProjectStorage(QgsProject.instance(), QDomDocument('plan'))

    def test_read_plans(self, storage: ProjectStorage):
        block_layer = QgsProject.instance().mapLayersByName('tuscaloosa_blocks — plans')[0]
        assign_layer = QgsProject.instance().mapLayersByName('test_assignments')[0]
        dist_layer = QgsProject.instance().mapLayersByName('test_districts')[0]
        plans = storage.readRedistrictingPlans()
        assert len(plans) == 1
        plan = plans[0]
        assert plan.name == 'test'
        assert plan.numDistricts == 5
        assert plan.numSeats == 5
        assert plan.popLayer == block_layer
        assert plan._assignLayer == assign_layer
        assert plan.distLayer == dist_layer
        assert len(plan.districts) == 6
        assert len(plan.dataFields) == 3 and plan.dataFields[0].layer == block_layer
        assert len(plan.geoFields) == 1 and plan.geoFields[0].layer == block_layer

    def test_read_active_plan(self, storage: ProjectStorage):
        u = storage.readActivePlan()
        assert str(u) == '65a4a8c5-0fbe-4bfb-ae7f-3a5e7562f1aa'

    def test_write_plan(
        self,
        empty_storage: ProjectStorage,
        plan: RedistrictingPlan,
        dist_layer,
        block_layer
    ):
        empty_storage.writeRedistrictingPlans([plan])
        l, result = QgsProject.instance().readListEntry('redistricting', 'redistricting-plans')
        assert result
        assert len(l) == 1

        j = json.loads(l[0])
        assert 'name' in j
        assert j['pop-layer'] == block_layer.id()
        assert j['dist-layer'] == dist_layer.id()

    def test_write_active_plan(self, empty_storage: ProjectStorage, plan):
        empty_storage.writeActivePlan(plan)
        planid, _ = QgsProject.instance().readEntry('redistricting', 'active-plan')
        assert planid == str(plan.id)
