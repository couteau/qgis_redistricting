"""Test redististricting plugin district painter maptool"""
import pytest
from pytest_mock.plugin import MockerFixture
from pytestqt.plugin import QtBot
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtCore import (
    QPoint,
    Qt
)
from qgis.PyQt.QtGui import QMouseEvent

from redistricting.gui import (
    PaintDistrictsTool,
    PaintMode
)
from redistricting.models import RedistrictingPlan
from redistricting.services import PlanAssignmentEditor

# pylint: disable=protected-access


class TestPaintTool:
    @pytest.fixture
    def tool(self, qgis_canvas, mock_plan: RedistrictingPlan) -> PaintDistrictsTool:
        mock_plan.delta.setAssignLayer(None)
        return PaintDistrictsTool(qgis_canvas, mock_plan)

    @pytest.fixture
    def active_tool(self, qgis_canvas: QgsMapCanvas, tool: PaintDistrictsTool,
                    qtbot: QtBot,  mocker: MockerFixture):
        with qtbot.wait_signal(tool.activated):
            qgis_canvas.setMapTool(tool)
        mocker.patch.object(tool, "_assignmentEditor", spec=PlanAssignmentEditor)
        return tool

    def test_create(self, tool: PaintDistrictsTool, qgis_canvas):
        assert tool.plan is not None
        assert tool._layer is not None  # pylint: disable=protected-access
        assert tool.parent() == qgis_canvas
        assert tool.paintMode == PaintMode.PaintByGeography

    def test_target_not_set_cannot_activate(self, tool: PaintDistrictsTool):
        tool.setTargetDistrict(None)
        assert not tool.canActivate()

    def test_target_set_can_activate(self, tool: PaintDistrictsTool):
        tool.setTargetDistrict(2)
        assert tool.canActivate()

    def test_set_fields(self, tool: PaintDistrictsTool):
        tool.setGeoField('geoid20')
        assert tool.geoField == 'geoid20'

        tool.setGeoField(None)
        assert tool.geoField is None

    def test_set_target_district(self, tool: PaintDistrictsTool):
        tool.setTargetDistrict(2)
        assert tool.targetDistrict() == 2

        tool.setTargetDistrict(None)
        assert tool.targetDistrict() is None

    def test_set_source_district(self, tool: PaintDistrictsTool):
        tool.setSourceDistrict(0)
        assert tool.sourceDistrict() == 0

        tool.setSourceDistrict(None)
        assert tool.sourceDistrict() is None

    def test_set_invalid_geofield_throws_exception(self, tool: PaintDistrictsTool, mock_plan):
        assert len(mock_plan.geoFields) > 0
        assert tool.plan == mock_plan
        with pytest.raises(ValueError):
            tool.setGeoField('district')

    def test_no_plan_geofields_can_set_any_geolayer_field(self, tool: PaintDistrictsTool, mock_plan):
        mock_plan.geoFields.clear()
        assert 'district' not in mock_plan.geoFields
        tool.setGeoField('district')
        assert tool.geoField == 'district'

    def test_activate(self, tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        tool.setTargetDistrict(2)
        assert tool.targetDistrict() == 2

        assert tool._assignmentEditor is None
        with qtbot.wait_signal(tool.activated):
            qgis_canvas.setMapTool(tool)
        assert tool.isActive()
        assert tool._assignmentEditor is not None

    def test_deactivate(self, active_tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        assert active_tool._assignmentEditor is not None
        with qtbot.wait_signal(active_tool.deactivated):
            qgis_canvas.unsetMapTool(active_tool)
        assert not active_tool.isActive()
        assert active_tool._assignmentEditor is None

    def test_keypress_esc_unsets_tool(self, active_tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        active_tool.setTargetDistrict(2)
        assert active_tool.isActive()
        with qtbot.wait_signal(qgis_canvas.keyPressed):
            qtbot.keyPress(qgis_canvas, Qt.Key_Escape)
        assert not active_tool.isActive()

    # pylint: disable=protected-access
    def test_mouse_press_without_target_no_edit(self,
                                                active_tool: PaintDistrictsTool,
                                                qgis_canvas: QgsMapCanvas,
                                                qtbot: QtBot):

        assignEditor = active_tool._assignmentEditor
        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)
        assignEditor.startEditCommand.assert_not_called()

        active_tool.setTargetDistrict(2)
        qtbot.mousePress(qgis_canvas.viewport(), Qt.RightButton)
        assignEditor.startEditCommand.assert_not_called()

        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)
        assignEditor.startEditCommand.assert_called_once()

    def test_mouse_press_select(self,
                                active_tool: PaintDistrictsTool,
                                qgis_canvas: QgsMapCanvas,
                                qtbot: QtBot):
        active_tool.setTargetDistrict(2)
        active_tool.paintMode = PaintMode.SelectByGeography
        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)
        assert active_tool._selectRect.topLeft() == qgis_canvas.viewport().rect().center()

    def test_mouse_release(self,
                           active_tool: PaintDistrictsTool,
                           qgis_canvas: QgsMapCanvas,
                           qtbot: QtBot):

        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())

        qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        active_tool._assignmentEditor.assignFeaturesToDistrict.assert_not_called()
        active_tool._assignmentEditor.getDistFeatures.assert_not_called()

        active_tool._assignmentEditor.assignFeaturesToDistrict.reset_mock()
        active_tool.setTargetDistrict(2)
        qtbot.mouseClick(qgis_canvas.viewport(), Qt.RightButton)
        active_tool._assignmentEditor.assignFeaturesToDistrict.assert_not_called()

        active_tool._assignmentEditor.assignFeaturesToDistrict.reset_mock()
        qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1000, 1000))
        active_tool._assignmentEditor.assignFeaturesToDistrict.assert_not_called()

        active_tool._assignmentEditor.assignFeaturesToDistrict.reset_mock()
        qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        active_tool._assignmentEditor.getDistFeatures.assert_not_called()
        active_tool._assignmentEditor.assignFeaturesToDistrict.assert_called_once()

    def test_mouse_release_geofield(self,
                                    active_tool: PaintDistrictsTool,
                                    qgis_canvas: QgsMapCanvas,
                                    qtbot: QtBot):
        active_tool.setTargetDistrict(2)
        active_tool.setGeoField('vtdid20')
        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())
        qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        active_tool._assignmentEditor.getDistFeatures.assert_called_once()
        active_tool._assignmentEditor.assignFeaturesToDistrict.assert_called_once()

    def test_mouse_release_select(self,
                                  active_tool: PaintDistrictsTool,
                                  qgis_canvas: QgsMapCanvas,
                                  qtbot: QtBot,
                                  mocker: MockerFixture):
        getDistFeatures = mocker.patch.object(active_tool._assignmentEditor, 'getDistFeatures')
        active_tool.setTargetDistrict(2)
        active_tool.paintMode = PaintMode.SelectByGeography
        with qtbot.wait_signal(active_tool._layer.selectionChanged):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        getDistFeatures.assert_not_called()

    def test_mouse_release_select_geofield(self,
                                           active_tool: PaintDistrictsTool,
                                           qgis_canvas: QgsMapCanvas,
                                           qtbot: QtBot,
                                           mocker: MockerFixture):
        getDistFeatures = mocker.patch.object(active_tool._assignmentEditor, 'getDistFeatures')
        active_tool.setTargetDistrict(2)
        active_tool.setGeoField('vtdid20')
        active_tool.paintMode = PaintMode.SelectByGeography
        with qtbot.wait_signal(active_tool._layer.selectionChanged):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        getDistFeatures.assert_called_once()

    def test_mouse_move(self,
                        active_tool: PaintDistrictsTool,
                        qgis_canvas: QgsMapCanvas,
                        qtbot: QtBot,
                        mocker: MockerFixture):

        assignFeaturesToDistrict: mocker.MagicMock = active_tool._assignmentEditor.assignFeaturesToDistrict
        getDistFeatures: mocker.MagicMock = active_tool._assignmentEditor.getDistFeatures
        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())

        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1000, 1000))
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(1000, 1000),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(1020, 1020),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1020, 1020))
        assignFeaturesToDistrict.assert_not_called()

        active_tool.setTargetDistrict(2)
        qtbot.mousePress(qgis_canvas.viewport(), Qt.RightButton, pos=QPoint(0, 0))
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                        Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                        Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        qtbot.mouseRelease(qgis_canvas.viewport(), Qt.RightButton, pos=qgis_canvas.viewport().rect().center())
        assignFeaturesToDistrict.assert_not_called()

        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())
        getDistFeatures.assert_not_called()
        assert assignFeaturesToDistrict.call_count == 2

    def test_mouse_move_select(self,
                               active_tool: PaintDistrictsTool,
                               qgis_canvas: QgsMapCanvas,
                               qtbot: QtBot,
                               mocker: MockerFixture):

        getDistFeatures = mocker.patch.object(active_tool._assignmentEditor, 'getDistFeatures')
        active_tool.setTargetDistrict(2)
        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())
        active_tool.paintMode = PaintMode.SelectByGeography

        with qtbot.assert_not_emitted(active_tool._layer.selectionChanged):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
            e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            assert active_tool._rubberBand is not None
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())

        with qtbot.wait_signal(active_tool._layer.selectionChanged):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
            e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            assert active_tool._rubberBand is not None
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())
        getDistFeatures.assert_not_called()

        active_tool.setGeoField('vtdid20')
        with qtbot.wait_signal(active_tool._layer.selectionChanged):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
            e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            assert active_tool._rubberBand is not None
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())
        getDistFeatures.assert_called_once()
