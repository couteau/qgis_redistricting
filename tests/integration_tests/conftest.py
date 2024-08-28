import pytest
from pytest_mock import MockerFixture
from qgis.PyQt.QtWidgets import QToolBar

from redistricting import services


@pytest.fixture
def patch_iface(qgis_iface,  mocker: MockerFixture):
    qgis_iface.addCustomActionForLayerType = mocker.MagicMock()
    qgis_iface.addCustomActionForLayer = mocker.MagicMock()
    qgis_iface.vectorMenu = mocker.MagicMock()
    qgis_iface.addPluginToVectorMenu = mocker.MagicMock()
    qgis_iface.removeDockWidget = mocker.MagicMock()
    qgis_iface.removePluginVectorMenu = mocker.MagicMock()
    qgis_iface.layerTreeView = mocker.MagicMock()


@pytest.fixture
def planmanager(patch_iface, qgis_new_project):  # pylint: disable=unused-argument, redefined-outer-name
    planManager = services.PlanManager()
    return planManager


@pytest.fixture
def toolbar(patch_iface):  # pylint: disable=unused-argument, redefined-outer-name
    tb = QToolBar("test toolbar")
    return tb


@pytest.fixture
def update_service():
    svc = services.DeltaUpdateService()
    return svc


@pytest.fixture
def assignment_service(update_service):  # pylint: disable=redefined-outer-name
    svc = services.AssignmentsService(update_service)
    return svc
