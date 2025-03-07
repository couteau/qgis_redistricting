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

from redistricting.models import RdsPlan
from redistricting.services import ProjectStorage


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
            project.read(str((datadir / 'test_project.qgz').resolve()))
        return ProjectStorage(project, doc)

    @pytest.fixture
    def empty_storage(self) -> ProjectStorage:
        return ProjectStorage(QgsProject.instance(), QDomDocument('plan'))

    def test_read_plans(self, storage: ProjectStorage):
        block_layer = QgsProject.instance().mapLayersByName('tuscaloosa — block20')[0]
        assign_layer = QgsProject.instance().mapLayersByName('Test Plan_assignments')[0]
        dist_layer = QgsProject.instance().mapLayersByName('Test Plan_districts')[0]
        plans = storage.readRedistrictingPlans()
        assert len(plans) == 1
        plan = plans[0]
        assert plan.name == 'Test Plan'
        assert plan.numDistricts == 5
        assert plan.numSeats == 5
        assert plan.popLayer == block_layer
        assert plan.assignLayer == assign_layer
        assert plan.distLayer == dist_layer
        assert len(plan.districts) == 6
        assert len(plan.dataFields) == 11 and plan.dataFields[0].layer == block_layer
        assert len(plan.geoFields) == 2 and plan.geoFields[0].layer == block_layer

    def test_read_active_plan(self, storage: ProjectStorage):
        u = storage.readActivePlan()
        assert str(u) == 'b63a8bbe-124d-4be2-953e-0a5b0d70fb91'

    def test_write_plan(
        self,
        empty_storage: ProjectStorage,
        plan: RdsPlan,
        dist_layer,
        block_layer
    ):
        empty_storage.writeRedistrictingPlans([plan])
        l, result = QgsProject.instance().readListEntry('redistricting', 'redistricting-plans')
        assert result
        assert len(l) == 1

        j = json.loads(l[0])
        assert 'name' in j
        assert j['geo-layer'] == block_layer.id()
        assert j['dist-layer'] == dist_layer.id()

    def test_write_active_plan(self, empty_storage: ProjectStorage, mock_plan):
        empty_storage.writeActivePlan(mock_plan)
        planid, _ = QgsProject.instance().readEntry('redistricting', 'active-plan')
        assert planid == str(mock_plan.id)
