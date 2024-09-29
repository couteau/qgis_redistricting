
from unittest.mock import PropertyMock

import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsProject
from qgis.PyQt.QtCore import pyqtBoundSignal
from qgis.PyQt.QtWidgets import QToolBar

from redistricting import services
from redistricting.models import RdsDistrict


class Fixtures:
    @pytest.fixture
    def active_plan(self, mocker: MockerFixture):
        return mocker.PropertyMock(return_value=None)

    @pytest.fixture
    def mock_district(self, mocker: MockerFixture):
        district = mocker.create_autospec(spec=RdsDistrict, instance=True)
        type(district).district = mocker.PropertyMock(return_value=1, )
        type(district).name = mocker.PropertyMock(return_value="District Name")
        type(district).description = mocker.PropertyMock(return_value="District description")
        return district

    @pytest.fixture
    def mock_planmanager(self, qgis_iface, qgis_new_project, active_plan, mocker: MockerFixture):  # pylint: disable=unused-argument
        qgis_iface.addCustomActionForLayerType = mocker.MagicMock()
        qgis_iface.addCustomActionForLayer = mocker.MagicMock()
        qgis_iface.vectorMenu = mocker.MagicMock()
        qgis_iface.addPluginToVectorMenu = mocker.MagicMock()
        qgis_iface.removeDockWidget = mocker.MagicMock()
        qgis_iface.removePluginVectorMenu = mocker.MagicMock()
        qgis_iface.layerTreeView = mocker.MagicMock()

        planManager = mocker.create_autospec(spec=services.PlanManager, instance=True)
        planManager.aboutToChangeActivePlan = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.activePlanChanged = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.planAdded = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.planRemoved = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.cleared = mocker.create_autospec(spec=pyqtBoundSignal)
        type(planManager).activePlan = active_plan
        return planManager

    @pytest.fixture
    def mock_planmanager_with_active_plan(self, qgis_iface, qgis_new_project, mock_district, active_plan: PropertyMock, mock_plan, mocker: MockerFixture):  # pylint: disable=unused-argument
        qgis_iface.addCustomActionForLayerType = mocker.MagicMock()
        qgis_iface.addCustomActionForLayer = mocker.MagicMock()
        qgis_iface.vectorMenu = mocker.MagicMock()
        qgis_iface.addPluginToVectorMenu = mocker.MagicMock()
        qgis_iface.removeDockWidget = mocker.MagicMock()
        qgis_iface.removePluginVectorMenu = mocker.MagicMock()
        qgis_iface.layerTreeView = mocker.MagicMock()

        planManager = mocker.create_autospec(spec=services.PlanManager, instance=True)
        planManager.aboutToChangeActivePlan = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.activePlanChanged = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.planAdded = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.planRemoved = mocker.create_autospec(spec=pyqtBoundSignal)
        planManager.cleared = mocker.create_autospec(spec=pyqtBoundSignal)
        active_plan.return_value = mock_plan
        mock_plan.districts.__getitem__.return_value = mock_district
        type(planManager).activePlan = active_plan

        return planManager

    @pytest.fixture
    def mock_project(self, mocker: MockerFixture):
        project = mocker.create_autospec(spec=QgsProject, instance=True)
        project.layersAdded = mocker.MagicMock()
        project.layersRemoved = mocker.MagicMock()
        project.cleared = mocker.MagicMock()
        return project

    @pytest.fixture
    def mock_toolbar(self, mocker: MockerFixture):
        toolbar = mocker.create_autospec(spec=QToolBar)
        return toolbar

    @pytest.fixture
    def mock_updater(self, mocker: MockerFixture) -> services.DistrictUpdater:
        updater = mocker.create_autospec(spec=services.DistrictUpdater, instance=True)
        updater.updateStarted = mocker.create_autospec(spec=pyqtBoundSignal)
        updater.updateComplete = mocker.create_autospec(spec=pyqtBoundSignal)
        updater.updateTerminated = mocker.create_autospec(spec=pyqtBoundSignal)
        return updater

    @pytest.fixture
    def mock_copier(self, mocker: MockerFixture) -> services.DistrictCopier:
        copier = mocker.create_autospec(spec=services.DistrictCopier, instance=True)
        return copier

    @pytest.fixture
    def mock_assignments_service(self, mocker: MockerFixture) -> services.AssignmentsService:
        assignments_service = mocker.create_autospec(spec=services.AssignmentsService, instance=True)
        return assignments_service
