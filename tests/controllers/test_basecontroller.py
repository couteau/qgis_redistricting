
import pytest
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot
from qgis.core import QgsProject
from qgis.gui import Qgis
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QProgressDialog,
    QPushButton,
    QToolBar
)

from redistricting.controllers.BaseCtlr import BaseController
from redistricting.services import PlanManager


class TestBaseController:
    @pytest.fixture
    def controller(self, qgis_iface, qgis_new_project, mocker: MockerFixture):  # pylint: disable=unused-argument
        planManager = mocker.create_autospec(spec=PlanManager)
        planManager.activePlan = None
        toolbar = mocker.create_autospec(spec=QToolBar)
        controller = BaseController(qgis_iface, QgsProject.instance(), planManager, toolbar)
        return controller

    def test_progress(self, controller: BaseController):
        d: QProgressDialog = controller.startProgress('Progress test')
        assert d is not None
        assert d.labelText() == 'Progress test'
        assert d.findChild(QPushButton) is not None
        assert d.findChild(QPushButton).text() == 'Cancel'

    def test_progress_no_cancel(self, controller: BaseController):
        d: QProgressDialog = controller.startProgress('Progress test', canCancel=False)
        assert d is not None
        assert d.labelText() == 'Progress test'
        assert d.findChild(QPushButton) is None

    def test_progress_cancel(self, controller: BaseController, qtbot: QtBot, qgis_iface):
        d: QProgressDialog = controller.startProgress('Progress test')
        with qtbot.waitSignal(d.canceled):
            b = d.findChild(QPushButton)
            qtbot.mouseClick(b, Qt.LeftButton)
        m = qgis_iface.messageBar().get_messages(Qgis.Warning)
        assert 'Canceled:Progress test canceled' in m

    def test_progress_create_new_dialog_closes_old_dialog(self, controller: BaseController, qtbot: QtBot):
        d1: QProgressDialog = controller.startProgress('Progress test1')
        with qtbot.wait_exposed(d1):
            d1.show()
        d2: QProgressDialog = controller.startProgress('Progress test2', canCancel=False)
        assert d1.isHidden()
        assert d2 != d1
        with qtbot.wait_exposed(d2):
            d2.show()
        d3: QProgressDialog = controller.startProgress('Progress test3')
        assert d2.isHidden()
        assert d3 != d2
        d3.hide()

    def test_check_active_plan(self, controller: BaseController, mock_plan, qgis_iface):
        result = controller.checkActivePlan('test')
        assert not result
        assert "Oops!:Cannot test: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        controller.planManager.activePlan = mock_plan

        result = controller.checkActivePlan('test')
        assert result
