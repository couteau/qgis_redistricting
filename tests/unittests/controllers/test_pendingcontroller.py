"""QGIS Redistricting Plugin - unit tests

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
import pandas as pd
import pytest
from pytest_mock import MockerFixture
from qgis.PyQt.QtCore import pyqtBoundSignal

from redistricting.controllers import PendingChangesController
from redistricting.models import (
    DeltaList,
    RdsPlan
)
from redistricting.services import (
    DeltaFieldFilterProxy,
    DeltaListModel,
    DeltaUpdateService
)

# pylint: disable=unused-argument, protected-access


class TestPendingChangesController:
    @pytest.fixture
    def mock_delta(self, mocker: MockerFixture):
        df = pd.DataFrame.from_records(
            [{
                'district': 1,
                'pop_total': 7,
                'new_pop_total': 95,
                'deviation': 5,
                'pct_deviation': 0.05,
                'vap_total': 5,
                'new_vap_total': 80,
                'vap_apblack': -5,
                'new_vap_apblack': 25,
                'pct_vap_apblack': 0.3125,
                'vap_nh_white': 3,
                'new_vap_nh_white': 40,
                'pct_vap_nh_white': 0.5,
                'vap_hispanic': 0,
                'new_vap_hispanic': 10,
                'pct_vap_hispanic': 0.125
            }],
            index='district'
        )
        delta = mocker.create_autospec(spec=DeltaList)
        delta.__bool__.return_value = True
        delta._data = df
        type(delta).updateStarted = mocker.create_autospec(spec=pyqtBoundSignal)
        type(delta).updateComplete = mocker.create_autospec(spec=pyqtBoundSignal)
        return delta

    @pytest.fixture
    def mock_update_service(self, mock_delta, mock_planmanager, mocker: MockerFixture) -> DeltaUpdateService:
        service = mocker.create_autospec(spec=DeltaUpdateService(mock_planmanager))
        service.getDelta.return_value = mock_delta
        return service

    @pytest.fixture
    def mock_model(self, mocker: MockerFixture) -> type[DeltaListModel]:
        mocker.patch('redistricting.controllers.PendingCtlr.DeltaFieldFilterProxy', spec=DeltaFieldFilterProxy)
        cls = mocker.patch('redistricting.controllers.PendingCtlr.DeltaListModel', spec=DeltaListModel)
        cls.return_value = mocker.create_autospec(spec=DeltaListModel())
        return cls

    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_update_service, mock_model, mocker: MockerFixture):
        mocker.patch('redistricting.controllers.PendingCtlr.DockPendingChanges')
        return PendingChangesController(qgis_iface, mock_project, mock_planmanager, mock_toolbar, mock_update_service)

    @pytest.fixture
    def controller_with_active_plan(self, qgis_iface, mock_planmanager_with_active_plan, mock_project, mock_toolbar, mock_update_service, mock_model, mocker: MockerFixture):
        mocker.patch('redistricting.controllers.PendingCtlr.DockPendingChanges')
        return PendingChangesController(qgis_iface, mock_project, mock_planmanager_with_active_plan, mock_toolbar, mock_update_service)

    def test_create(self, controller: PendingChangesController, mock_model):
        mock_model.assert_called_once()

    def test_load(self, controller, mock_planmanager, mock_update_service):
        mock_update_service.reset_mock()
        controller.load()
        mock_planmanager.activePlanChanged.connect.assert_called_once()
        mock_update_service.updateStarted.connect.assert_called_once()
        mock_update_service.updateCompleted.connect.assert_called_once()
        mock_update_service.updateTerminated.connect.assert_called_once()

    def test_unload(self, controller, mock_planmanager, mock_update_service):
        mock_update_service.reset_mock()
        controller.load()
        controller.unload()
        mock_planmanager.activePlanChanged.disconnect.assert_called_once()
        mock_update_service.updateStarted.disconnect.assert_called_once()
        mock_update_service.updateCompleted.disconnect.assert_called_once()
        mock_update_service.updateTerminated.disconnect.assert_called_once()

    def test_active_plan_changed(self, controller_with_active_plan: PendingChangesController, mock_update_service: DeltaUpdateService, mock_plan, mocker: MockerFixture):
        controller_with_active_plan.load()
        plan = mocker.PropertyMock(spec=RdsPlan)
        type(controller_with_active_plan.dockwidget).plan = plan
        controller_with_active_plan.activePlanChanged(mock_plan)
        plan.assert_called_once_with(mock_plan)
        mock_update_service.getDelta.assert_called_once_with(mock_plan)
        controller_with_active_plan.model.setPlan.assert_called_once_with(
            mock_plan, mock_update_service.getDelta.return_value)

    def test_active_plan_changed_none(self, controller_with_active_plan: PendingChangesController, mock_update_service: DeltaUpdateService, mock_plan, mocker: MockerFixture):
        controller_with_active_plan.load()
        plan = mocker.PropertyMock(spec=RdsPlan)
        type(controller_with_active_plan.dockwidget).plan = plan
        plan.return_value = mock_plan
        controller_with_active_plan.activePlanChanged(None)
        plan.assert_called_once_with(None)
        mock_update_service.getDelta.assert_not_called()
        controller_with_active_plan.model.setPlan.assert_called_once_with(None, None)

    def test_update_delta(self, controller_with_active_plan: PendingChangesController, mock_update_service: DeltaUpdateService, mock_plan, mock_delta):
        controller_with_active_plan.load()
        controller_with_active_plan.startDelta(mock_plan)
        controller_with_active_plan.model.setDelta.assert_called_once_with(mock_delta)
