"""QGIS Redistricting Plugin - common fixtures for integration tests

Copyright 2022-2024, Stuart C. Naifeh

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
import pytest
from qgis.PyQt.QtWidgets import QToolBar

from redistricting import services

# pylint: disable=unused-argument, redefined-outer-name


@pytest.fixture
def planmanager(qgis_new_project):
    planManager = services.PlanManager()
    return planManager


@pytest.fixture
def layertreemanager(qgis_new_project):
    svc = services.LayerTreeManager()
    return svc


@pytest.fixture
def styler_service(planmanager):
    svc = services.PlanStylerService(planmanager)
    return svc


@pytest.fixture
def toolbar():  # pylint: disable=unused-argument, redefined-outer-name
    tb = QToolBar("test toolbar")
    return tb


@pytest.fixture
def delta_update_service(planmanager):
    svc = services.DeltaUpdateService(planmanager)
    return svc


@pytest.fixture
def assignment_service(delta_update_service: services.DeltaUpdateService):  # pylint: disable=redefined-outer-name
    svc = services.AssignmentsService()
    svc.editingStarted.connect(delta_update_service.watchPlan)
    svc.editingStopped.connect(delta_update_service.unwatchPlan)
    return svc


@pytest.fixture
def district_update_service():
    svc = services.DistrictUpdater()
    return svc


@pytest.fixture
def import_service(district_update_service: services.DistrictUpdater):
    svc = services.PlanImportService()
    svc.importComplete.connect(lambda plan: district_update_service.updateDistricts(
        plan, needDemographics=True, needGeometry=True, needSplits=True, force=True
    ))
