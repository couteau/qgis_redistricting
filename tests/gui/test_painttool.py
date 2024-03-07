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

from redistricting.core import RedistrictingPlan
from redistricting.gui import (
    PaintDistrictsTool,
    PaintMode
)


class TestPaintTool:
    @pytest.fixture
    def tool(self, qgis_canvas, plan: RedistrictingPlan) -> PaintDistrictsTool:
        plan.delta.detachSignals()
        return PaintDistrictsTool(qgis_canvas, plan)

    @pytest.fixture
    def active_tool(self, qgis_canvas: QgsMapCanvas, tool: PaintDistrictsTool,
                    qtbot: QtBot, mocker: MockerFixture):
        mocker.patch('redistricting.gui.PaintTool.PlanAssignmentEditor')
        with qtbot.wait_signal(tool.activated):
            qgis_canvas.setMapTool(tool)
        return tool

    def test_create(self, tool: PaintDistrictsTool, qgis_canvas):
        assert tool.plan is not None
        assert tool._layer is not None  # pylint: disable=protected-access
        assert tool.parent() == qgis_canvas
        assert tool.paintMode == PaintMode.PaintByGeography

    def test_can_activate(self, tool: PaintDistrictsTool):
        assert not tool.canActivate()
        tool.setTargetDistrict(2)
        assert tool.canActivate()

    def test_set_fields(self, tool: PaintDistrictsTool):
        tool.setTargetDistrict(2)
        assert tool.targetDistrict() == 2
        tool.setSourceDistrict(0)
        assert tool.sourceDistrict() == 0
        tool.setGeoField('geoid20')
        assert tool.geoField == 'geoid20'

        tool.setGeoField(None)
        assert tool.geoField is None
        tool.setSourceDistrict(None)
        assert tool.sourceDistrict() is None
        tool.setTargetDistrict(None)
        assert tool.targetDistrict() is None

    def test_set_invalid_geofield_throws_exception(self, tool: PaintDistrictsTool, plan):
        with pytest.raises(ValueError):
            tool.setGeoField('district')
        plan.geoFields.clear()
        tool.setGeoField('district')
        assert tool.geoField == 'district'

    def test_activate(self, tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot, mocker: MockerFixture):
        cls = mocker.patch('redistricting.gui.PaintTool.PlanAssignmentEditor')
        tool.setTargetDistrict(2)
        assert tool.targetDistrict() == 2

        with qtbot.wait_signal(tool.activated):
            qgis_canvas.setMapTool(tool)
        assert tool.isActive()
        cls.assert_called_once_with(tool.plan, tool)

        with qtbot.wait_signal(tool.deactivated):
            qgis_canvas.unsetMapTool(tool)
        assert not tool.isActive()
        assert tool._assignmentEditor is None  # pylint: disable=protected-access

    def test_keypress_esc_unsets_tool(self, active_tool: PaintDistrictsTool, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        active_tool.setTargetDistrict(2)
        with qtbot.wait_signal(qgis_canvas.keyPressed):
            qtbot.keyPress(qgis_canvas, Qt.Key_Escape)
        assert not active_tool.isActive()

    # pylint: disable=protected-access
    def test_mouse_press(self,
                         active_tool: PaintDistrictsTool,
                         qgis_canvas: QgsMapCanvas,
                         qtbot: QtBot):
        with qtbot.assert_not_emitted(active_tool._layer.editCommandStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)

        active_tool.setTargetDistrict(2)
        with qtbot.assert_not_emitted(active_tool._layer.editCommandStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.RightButton)

        with qtbot.wait_signal(active_tool._layer.editCommandStarted):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton)

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
                           qtbot: QtBot,
                           mocker: MockerFixture):
        assignFeaturesToDistrict = mocker.patch.object(active_tool._assignmentEditor, 'assignFeaturesToDistrict')
        getDistFeatures = mocker.patch.object(active_tool._assignmentEditor, 'getDistFeatures')
        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())

        with qtbot.assert_not_emitted(active_tool._layer.editCommandDestroyed):
            with qtbot.assert_not_emitted(active_tool._layer.editCommandEnded):
                qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)

        active_tool.setTargetDistrict(2)
        with qtbot.assert_not_emitted(active_tool._layer.editCommandDestroyed):
            with qtbot.assert_not_emitted(active_tool._layer.editCommandEnded):
                qtbot.mouseClick(qgis_canvas.viewport(), Qt.RightButton)

        with qtbot.wait_signal(active_tool._layer.editCommandDestroyed):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1000, 1000))

        with qtbot.wait_signals([active_tool._layer.editCommandEnded, qgis_canvas.mapCanvasRefreshed]):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        getDistFeatures.assert_not_called()
        assignFeaturesToDistrict.assert_called_once()

    def test_mouse_release_geofield(self,
                                    active_tool: PaintDistrictsTool,
                                    qgis_canvas: QgsMapCanvas,
                                    qtbot: QtBot,
                                    mocker: MockerFixture):
        getDistFeatures = mocker.patch.object(active_tool._assignmentEditor, 'getDistFeatures')
        active_tool.setTargetDistrict(2)
        active_tool.setGeoField('vtdid20')
        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())
        with qtbot.wait_signals([active_tool._layer.editCommandEnded, qgis_canvas.mapCanvasRefreshed]):
            qtbot.mouseClick(qgis_canvas.viewport(), Qt.LeftButton)
        getDistFeatures.assert_called_once()

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

        assignFeaturesToDistrict = mocker.patch.object(active_tool._assignmentEditor, 'assignFeaturesToDistrict')
        getDistFeatures = mocker.patch.object(active_tool._assignmentEditor, 'getDistFeatures')
        qgis_canvas.setDestinationCrs(active_tool._layer.crs())
        qgis_canvas.setExtent(active_tool._layer.extent())

        with qtbot.assert_not_emitted(qgis_canvas.mapCanvasRefreshed):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1000, 1000))
            e = QMouseEvent(QMouseEvent.MouseMove, QPoint(1000, 1000),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            e = QMouseEvent(QMouseEvent.MouseMove, QPoint(1020, 1020),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.LeftButton, pos=QPoint(1020, 1020))

        active_tool.setTargetDistrict(2)
        with qtbot.assert_not_emitted(qgis_canvas.mapCanvasRefreshed):
            qtbot.mousePress(qgis_canvas.viewport(), Qt.RightButton, pos=QPoint(0, 0))
            e = QMouseEvent(QMouseEvent.MouseMove, QPoint(0, 0),
                            Qt.RightButton, Qt.RightButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            e = QMouseEvent(QMouseEvent.MouseMove, qgis_canvas.viewport().rect().center(),
                            Qt.RightButton, Qt.RightButton, Qt.NoModifier)
            qgis_canvas.mouseMoveEvent(e)
            qtbot.mouseRelease(qgis_canvas.viewport(), Qt.RightButton, pos=qgis_canvas.viewport().rect().center())

        with qtbot.wait_signals([active_tool._layer.editCommandEnded, qgis_canvas.mapCanvasRefreshed]):
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
