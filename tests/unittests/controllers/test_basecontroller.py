
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
from redistricting.services import (
    ErrorListMixin,
    PlanManager
)


class TestBaseController:
    @pytest.fixture
    def controller(self, qgis_iface, qgis_new_project, mocker: MockerFixture):  # pylint: disable=unused-argument
        # mocker.patch('redistricting.controllers.BaseCtlr.RdsProgressDialog', spec=QProgressDialog)
        planManager = mocker.create_autospec(spec=PlanManager)
        planManager.activePlan = None
        toolbar = mocker.create_autospec(spec=QToolBar)
        controller = BaseController(qgis_iface, QgsProject.instance(), planManager, toolbar)
        return controller

    def test_progress(self, controller: BaseController, qtbot: QtBot):
        d: QProgressDialog = controller.startProgress('Progress test')
        with qtbot.waitActive(d):
            d.show()
        assert d is not None
        assert d.labelText() == 'Progress test'
        assert d.findChild(QPushButton) is not None
        assert d.findChild(QPushButton).text() == 'Cancel'
        d.hide()
        del d

    def test_progress_no_cancel(self, controller: BaseController, qtbot: QtBot):
        d: QProgressDialog = controller.startProgress('Progress test', canCancel=False)
        with qtbot.waitActive(d):
            d.show()
        assert d is not None
        assert d.labelText() == 'Progress test'
        assert d.findChild(QPushButton) is None
        d.hide()
        del d

    def test_progress_cancel(self, controller: BaseController, qtbot: QtBot, qgis_iface):
        d: QProgressDialog = controller.startProgress('Progress test')
        with qtbot.waitActive(d):
            d.show()
        with qtbot.waitSignal(d.canceled):
            b = d.findChild(QPushButton)
            qtbot.mouseClick(b, Qt.LeftButton)
        m = qgis_iface.messageBar().get_messages(Qgis.Warning)
        assert 'Canceled:Progress test canceled' in m
        d.hide()
        del d

    def test_progress_set_value_after_cancel_returns(self, controller: BaseController, qtbot: QtBot, qgis_iface):
        d: QProgressDialog = controller.startProgress('Progress test')
        with qtbot.waitActive(d):
            d.show()
        d.setValue(50)
        assert d.value() == 50
        with qtbot.waitSignal(d.canceled):
            b = d.findChild(QPushButton)
            qtbot.mouseClick(b, Qt.LeftButton)
            d.setValue(100)
        m = qgis_iface.messageBar().get_messages(Qgis.Warning)
        assert 'Canceled:Progress test canceled' in m
        assert d.value() == -1
        d.hide()
        del d

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
        with qtbot.waitActive(d3):
            d3.show()
        assert d2.isHidden()
        assert d3 != d2
        d3.hide()

        del d1
        del d2
        del d3

    def test_check_active_plan(self, controller: BaseController, mock_plan, qgis_iface):
        result = controller.checkActivePlan('test')
        assert not result
        assert "Oops!:Cannot test: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        controller.planManager.activePlan = mock_plan

        result = controller.checkActivePlan('test')
        assert result

    def test_push_errors(self, controller: BaseController, qgis_iface):
        controller.pushErrors([("Error message", Qgis.Critical)], "Error!", Qgis.Warning)
        assert "Error!:Error message" in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_progress_error_mixin_supplies_error_list(self, controller: BaseController, qtbot: QtBot, qgis_iface):
        mixin = ErrorListMixin()
        mixin.setError("Error message", Qgis.Warning)
        d: QProgressDialog = controller.startProgress('Progress test', errorList=mixin)
        with qtbot.waitActive(d):
            d.show()
        with qtbot.waitSignal(d.canceled):
            b = d.findChild(QPushButton)
            qtbot.mouseClick(b, Qt.LeftButton)
        assert "Canceled:Error message" in qgis_iface.messageBar().get_messages(Qgis.Warning)
        d.hide()
        del d

    def test_push_errors_empty_list_returns(self, controller: BaseController, qgis_iface):
        # qgis_iface is a session scoped fixture -- meaning the message log is not cleared
        # between tests, so we can't check for an empty message log
        l = len(qgis_iface.messageBar().get_messages(Qgis.Warning))
        controller.pushErrors([], "Error!", Qgis.Warning)
        assert len(qgis_iface.messageBar().get_messages(Qgis.Warning)) == l

    def test_push_errors_no_title_uses_default(self, controller: BaseController, qgis_iface):
        controller.pushErrors([("Error message", Qgis.Critical)],  level=Qgis.Warning)
        assert "Error:Error message" in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_push_errors_no_level_uses_first_error(self, controller: BaseController, qgis_iface):
        controller.pushErrors([("Error message", Qgis.Critical), ("Warning message", Qgis.Warning)])
        assert "Error:Error message" in qgis_iface.messageBar().get_messages(Qgis.Critical)

    def test_end_progress(self, controller: BaseController, qtbot: QtBot):
        d: QProgressDialog = controller.startProgress('Progress test')
        with qtbot.waitActive(d):
            d.show()
        controller.endProgress()
        assert controller.dlg is None
        assert d.isHidden()

        del d
        d: QProgressDialog = controller.startProgress('Progress test')
        with qtbot.waitActive(d):
            d.show()
        controller.endProgress(d)
        assert controller.dlg is None
        assert d.isHidden()
        del d
