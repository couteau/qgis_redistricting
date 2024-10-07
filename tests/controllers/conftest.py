import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import QToolBar

from redistricting import services


@pytest.fixture
def planmanager(qgis_iface, qgis_new_project, mocker: MockerFixture):  # pylint: disable=unused-argument
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
    type(planManager).activePlan = mocker.PropertyMock(return_value=None)
    return planManager


@pytest.fixture
def planmanager_with_active_plan(qgis_iface, qgis_new_project, mock_plan, mocker: MockerFixture):  # pylint: disable=unused-argument
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
    type(planManager).activePlan = mocker.PropertyMock(return_value=mock_plan)

    return planManager


@pytest.fixture
def mock_project(mocker: MockerFixture):
    project = mocker.create_autospec(spec=QgsProject, instance=True)
    project.layersAdded = mocker.MagicMock()
    project.layersRemoved = mocker.MagicMock()
    project.cleared = mocker.MagicMock()
    return project


@pytest.fixture
def mock_toolbar(mocker: MockerFixture):
    toolbar = mocker.create_autospec(spec=QToolBar)
    return toolbar
