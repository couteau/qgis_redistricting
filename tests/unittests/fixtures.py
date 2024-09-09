
from unittest.mock import PropertyMock

import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsProject
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
        planManager.activePlanChanged = mocker.MagicMock()
        planManager.planAdded = mocker.MagicMock()
        planManager.planRemoved = mocker.MagicMock()
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
        planManager.activePlanChanged = mocker.MagicMock()
        planManager.planAdded = mocker.MagicMock()
        planManager.planRemoved = mocker.MagicMock()
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
