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
import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsApplication
from qgis.gui import (
    QgsMapCanvas,
    QgsMapMouseEvent
)
from qgis.PyQt.QtCore import (
    QEvent,
    QModelIndex,
    QPoint,
    Qt
)
from qgis.PyQt.QtGui import QContextMenuEvent
from qgis.PyQt.QtWidgets import (
    QAction,
    QMenu
)

from redistricting.controllers import (
    DistrictController,
    EditAssignmentsController
)
from redistricting.models import RdsPlan
from redistricting.services import DistrictCopier


class TestDistrictController:
    @pytest.fixture(autouse=True)
    def dockwidget(self, mocker: MockerFixture):
        widget_class = mocker.patch('redistricting.controllers.district.DockDistrictDataTable')
        return widget_class

    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_assignments_service, mock_copier, mock_updater):
        controller = DistrictController(qgis_iface, mock_project, mock_planmanager, mock_toolbar,
                                        mock_assignments_service, mock_copier, mock_updater)
        controller.load()
        yield controller
        controller.unload()

    @pytest.fixture
    def controller_with_active_plan(self, qgis_iface, mock_planmanager_with_active_plan, mock_project, mock_toolbar, mock_assignments_service, mock_copier, mock_updater):
        controller = DistrictController(qgis_iface, mock_project, mock_planmanager_with_active_plan, mock_toolbar,
                                        mock_assignments_service, mock_copier, mock_updater)
        controller.load()
        yield controller
        controller.unload()

    def test_active_plan_changed(self, controller_with_active_plan: DistrictController, mock_plan, mocker: MockerFixture):
        plan = mocker.PropertyMock(spec=RdsPlan)
        type(controller_with_active_plan.dockwidget).plan = plan
        controller_with_active_plan.activePlanChanged(mock_plan)
        plan.assert_called_once()

    def test_add_canvas_context_menu_items(self, controller_with_active_plan: DistrictController, qgis_canvas: QgsMapCanvas, mock_copier: DistrictCopier):
        menu = QMenu("test")
        event = QgsMapMouseEvent(qgis_canvas, QEvent.Type.MouseButtonPress, QPoint(0, 0), Qt.MouseButton.RightButton)
        controller_with_active_plan.addCanvasContextMenuItems(menu, event)
        mock_copier.canCopyAssignments.assert_called_once()
        mock_copier.canPasteAssignments.assert_called_once()

    def test_add_canvas_context_menu_items_no_active_plan_returns(self, controller: DistrictController, qgis_canvas: QgsMapCanvas, mock_copier: DistrictCopier):
        assert controller.planManager.activePlan is None
        menu = QMenu("test")
        event = QgsMapMouseEvent(qgis_canvas, QEvent.Type.MouseButtonPress, QPoint(0, 0), Qt.MouseButton.RightButton)
        controller.addCanvasContextMenuItems(menu, event)
        mock_copier.canCopyAssignments.assert_not_called()
        mock_copier.canPasteAssignments.assert_not_called()

    def test_zoom_to_district(self, controller_with_active_plan: DistrictController, mocker: MockerFixture):
        canvas = mocker.patch.object(controller_with_active_plan, "canvas",
                                     mocker.create_autospec(spec=controller_with_active_plan.canvas, instance=True))
        controller_with_active_plan.zoomToDistrict(1)
        canvas.zoomToFeatureIds.assert_called_once()

    def test_zoom_to_district_no_active_plan_returns(self, controller: DistrictController, active_plan, mocker: MockerFixture):
        canvas = mocker.patch.object(controller, "canvas", mocker.create_autospec(
            spec=controller.canvas, instance=True))
        controller.zoomToDistrict(None)
        canvas.zoomToFeatureIds.assert_not_called()
        active_plan.assert_called_once()
        active_plan.districts.assert_not_called()

    def test_zoom_to_district_no_argument_uses_action(self, controller_with_active_plan: DistrictController, mocker: MockerFixture):
        action = mocker.create_autospec(spec=QAction, instance=True)
        action.data.return_value = 1
        canvas = mocker.patch.object(controller_with_active_plan, "canvas",
                                     mocker.create_autospec(spec=controller_with_active_plan.canvas, instance=True))
        sender = mocker.patch.object(controller_with_active_plan, "sender")
        sender.return_value = action
        controller_with_active_plan.zoomToDistrict(None)
        action.data.assert_called_once()
        canvas.zoomToFeatureIds.assert_called_once()

    def test_zoom_to_district_invalid_argument_raises_error(self, controller_with_active_plan: DistrictController,  mocker: MockerFixture):
        canvas = mocker.patch.object(controller_with_active_plan, "canvas",
                                     mocker.create_autospec(spec=controller_with_active_plan.canvas, instance=True))
        with pytest.raises(TypeError):
            controller_with_active_plan.zoomToDistrict("A")

        canvas.zoomToFeatureIds.assert_not_called()

        with pytest.raises(ValueError):
            controller_with_active_plan.zoomToDistrict(0)

        canvas.zoomToFeatureIds.assert_not_called()

        action = mocker.create_autospec(spec=QAction, instance=True)
        action.data.return_value = None
        sender = mocker.patch.object(controller_with_active_plan, "sender")
        sender.return_value = action

        with pytest.raises(TypeError):
            controller_with_active_plan.zoomToDistrict(None)

    def test_flash_district(self, controller_with_active_plan: DistrictController, mocker: MockerFixture):
        canvas = mocker.patch.object(controller_with_active_plan, "canvas",
                                     mocker.create_autospec(spec=controller_with_active_plan.canvas, instance=True))
        controller_with_active_plan.flashDistrict(1)
        canvas.flashFeatureIds.assert_called_once()

    def test_context_menu_event(self, controller: DistrictController, mocker: MockerFixture):
        mocker.patch('redistricting.controllers.district.QMenu')
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(0, 0),
                                  QPoint(0, 0), Qt.KeyboardModifier.NoModifier)
        assert controller.eventFilter(controller.dockwidget, event)

        event = QEvent(QEvent.Type.MouseButtonPress)
        assert not controller.eventFilter(controller.dockwidget, event)

    def test_data_table_context_menu(self, controller: DistrictController, mocker: MockerFixture):
        menu = mocker.patch('redistricting.controllers.district.QMenu')
        controller.load()
        assert menu.return_value.addAction.call_count == 5
        menu.return_value.addAction.assert_any_call(controller.actionCopyDistrict)

    def test_copy_data_to_clipboard(self, controller_with_active_plan: DistrictController, mocker: MockerFixture):
        clipboard = mocker.patch('redistricting.controllers.district.DistrictClipboardAccess')
        mime = mocker.patch('redistricting.controllers.district.QMimeData')
        set_mime = mocker.patch.object(QgsApplication.instance().clipboard(), 'setMimeData')
        controller_with_active_plan.copyToClipboard()
        clipboard.assert_called_once()
        clipboard.return_value.getAsHtml.assert_called_once()
        clipboard.return_value.getAsCsv.assert_called_once()
        mime.assert_called_once()
        set_mime.assert_called_once()

    def test_copy_data_to_clipboard_with_selection(self, controller_with_active_plan: DistrictController, dockwidget, mocker: MockerFixture):
        clipboard = mocker.patch('redistricting.controllers.district.DistrictClipboardAccess')
        mime = mocker.patch('redistricting.controllers.district.QMimeData')
        set_mime = mocker.patch.object(QgsApplication.instance().clipboard(), 'setMimeData')
        index = mocker.create_autospec(spec=QModelIndex, instance=True)
        index.row.return_value = 1
        index.column.return_value = 5
        selection = [index]
        dockwidget.return_value.tblPlanStats.hasFocus.return_value = False
        dockwidget.return_value.tblDataTable.selectedIndexes.return_value = selection
        controller_with_active_plan.copySelection()
        clipboard.assert_called_once()
        clipboard.return_value.getAsHtml.assert_called_once()
        clipboard.return_value.getAsCsv.assert_called_once()
        mime.assert_called_once()
        set_mime.assert_called_once()

    def test_recalculate(self, controller_with_active_plan, mock_updater):
        controller_with_active_plan.recalculate()
        mock_updater.updateDistricts.assert_called_once()

    def test_edit_district(self, controller_with_active_plan: DistrictController, qgis_iface, mock_project, mock_planmanager, mock_toolbar, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.controllers.edit.DlgNewDistrict')
        # pylint: disable-next=unused-variable
        editctlr = EditAssignmentsController(
            qgis_iface, mock_project, mock_planmanager, mock_toolbar, mocker.MagicMock())
        index = mocker.create_autospec(spec=QModelIndex, instance=True)
        index.row.return_value = 1
        index.column.return_value = 1

        controller_with_active_plan.editDistrict(index)
        dlg.assert_called_once()
