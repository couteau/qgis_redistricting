"""Test redististricting plugin district painter maptool"""
import pytest
from pytest_mock import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import QgsVectorLayer
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
from redistricting.models import RdsPlan

# pylint: disable=protected-access


class TestPaintTool:
    @pytest.fixture
    def tool(self, qgis_canvas) -> PaintDistrictsTool:
        return PaintDistrictsTool(qgis_canvas)

    @pytest.fixture
    def active_tool(self, qgis_canvas: QgsMapCanvas, tool: PaintDistrictsTool, assign_layer: QgsVectorLayer, qtbot: QtBot):
        tool._layer = assign_layer
        with qtbot.wait_signal(tool.activated):
            qgis_canvas.setMapTool(tool)
        return tool

    @pytest.fixture
    def active_tool_with_plan(
        self,
        qgis_canvas: QgsMapCanvas,
        plan: RdsPlan,
        qtbot: QtBot
    ) -> PaintDistrictsTool:
        t = PaintDistrictsTool(qgis_canvas)
        t.plan = plan
        with qtbot.wait_signal(t.activated):
            qgis_canvas.setMapTool(t)
        return t

    def test_create(self, tool: PaintDistrictsTool, qgis_canvas):
        assert tool.plan is None
        assert tool._layer is None
        assert tool.parent() == qgis_canvas
        assert tool.paintMode == PaintMode.PaintByGeography

    def test_set_plan(self, tool: PaintDistrictsTool, mock_plan: RdsPlan):
        tool.plan = mock_plan
        assert tool._layer == mock_plan.assignLayer

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

    def test_activate(self, tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        tool.setTargetDistrict(2)
        assert tool.targetDistrict() == 2

        with qtbot.wait_signal(tool.activated):
            qgis_canvas.setMapTool(tool)
        assert tool.isActive()

    def test_deactivate(self, active_tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        assert active_tool.isActive()
        with qtbot.wait_signal(active_tool.deactivated):
            qgis_canvas.unsetMapTool(active_tool)
        assert not active_tool.isActive()

    def test_keypress_esc_unsets_tool(self, active_tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        active_tool.setTargetDistrict(2)
        assert active_tool.isActive()
        with qtbot.wait_signal(qgis_canvas.keyPressed):
            qtbot.keyPress(qgis_canvas, Qt.Key_Escape)
        assert not active_tool.isActive()

    def test_mouse_press_without_target_no_edit(self,
                                                active_tool: PaintDistrictsTool,
                                                qgis_canvas: QgsMapCanvas,
                                                qtbot: QtBot):

        with qtbot.assertNotEmitted(active_tool.paintingStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)

        active_tool.setTargetDistrict(2)
        with qtbot.assertNotEmitted(active_tool.paintingStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.RightButton)

        with qtbot.waitSignal(active_tool.paintingStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)

    def test_mouse_press_select(
        self,
        active_tool: PaintDistrictsTool,
        qgis_canvas: QgsMapCanvas,
        qtbot: QtBot
    ):
        active_tool.setTargetDistrict(2)
        active_tool.paintMode = PaintMode.SelectByGeography
        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)
        assert active_tool._selectRect.topLeft() == qgis_canvas.viewport().rect().center()

    # @pytest.mark.qgis_show_map(timeout=1)
    def test_mouse_release(self,
                           active_tool_with_plan: PaintDistrictsTool,
                           qgis_canvas: QgsMapCanvas,
                           qgis_parent,
                           qtbot: QtBot):

        qgis_canvas.setDestinationCrs(active_tool_with_plan._layer.crs())
        qgis_canvas.setExtent(active_tool_with_plan._layer.extent())
        qgis_parent.show()

        with qtbot.assertNotEmitted(active_tool_with_plan.paintingComplete):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)

        active_tool_with_plan.setTargetDistrict(2)
        with qtbot.assertNotEmitted(active_tool_with_plan.paintingComplete):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.RightButton)

        with qtbot.assertNotEmitted(active_tool_with_plan.paintingComplete):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1000, 1000))

        with qtbot.waitSignals([active_tool_with_plan.paintingStarted, active_tool_with_plan.paintingComplete, active_tool_with_plan.paintFeatures]):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)

        qgis_parent.hide()

    # @pytest.mark.qgis_show_map(timeout=1)
    def test_mouse_release_select(self,
                                  active_tool_with_plan: PaintDistrictsTool,
                                  qgis_canvas: QgsMapCanvas,
                                  qgis_parent,
                                  qtbot: QtBot):

        qgis_parent.show()
        active_tool_with_plan.setTargetDistrict(2)
        active_tool_with_plan.paintMode = PaintMode.SelectByGeography
        with qtbot.wait_signal(active_tool_with_plan.selectFeatures):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        qgis_parent.hide()

    # @pytest.mark.qgis_show_map(timeout=1)
    def test_mouse_move(
        self,
        active_tool_with_plan: PaintDistrictsTool,
        qgis_canvas: QgsMapCanvas,
        qgis_parent,
        qtbot: QtBot,
        mocker: MockerFixture
    ):

        paintFeatures = mocker.patch.object(active_tool_with_plan, "_paintFeatures")

        qgis_canvas.setDestinationCrs(active_tool_with_plan._layer.crs())
        qgis_canvas.setExtent(active_tool_with_plan._layer.extent())
        qgis_parent.show()

        qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1000, 1000))
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(1000, 1000),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(1020, 1020),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1020, 1020))
        paintFeatures.assert_not_called()

        active_tool_with_plan.setTargetDistrict(2)
        qtbot.mousePress(qgis_canvas.viewport(), Qt.RightButton, pos=QPoint(0, 0))
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                        Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                        Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        qtbot.mouseRelease(qgis_canvas.viewport(), Qt.RightButton, pos=qgis_canvas.viewport().rect().center())
        paintFeatures.assert_not_called()

        with qtbot.waitSignal(active_tool_with_plan.paintingStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
        e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        qgis_canvas.mouseMoveEvent(e)
        with qtbot.waitSignal(active_tool_with_plan.paintingComplete):
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())
        qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())
        assert paintFeatures.call_count == 2

        qgis_parent.hide()

    # @pytest.mark.qgis_show_map(timeout=1)
    def test_mouse_move_select(self,
                               active_tool_with_plan: PaintDistrictsTool,
                               qgis_canvas: QgsMapCanvas,
                               qgis_parent,
                               qtbot: QtBot):

        active_tool_with_plan.setTargetDistrict(2)
        qgis_canvas.setDestinationCrs(active_tool_with_plan._layer.crs())
        qgis_canvas.setExtent(active_tool_with_plan._layer.extent())
        qgis_parent.show()
        active_tool_with_plan.paintMode = PaintMode.SelectByGeography

        with qtbot.assertNotEmitted(active_tool_with_plan.selectFeatures):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
            e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            assert active_tool_with_plan._rubberBand is not None
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())

        with qtbot.waitSignal(active_tool_with_plan.selectFeatures):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(0, 0))
            e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            assert active_tool_with_plan._rubberBand is not None
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=qgis_canvas.viewport().rect().center())
            qgis_parent.hide()