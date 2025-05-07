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
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer
)
from qgis.PyQt.QtGui import QColor

from redistricting.services import PlanStylerService

# pylint: disable=unused-argument,protected-access


class TestStyler:
    def test_createstyler(self, mock_planmanager):
        styler = PlanStylerService(mock_planmanager)
        assert styler._assignRenderer is None
        assert styler._distRenderer is None
        assert styler._labeling is None
        assert styler._numDistricts == 0

    def test_copy_styles(self, mock_planmanager, mock_plan):
        styler = PlanStylerService(mock_planmanager)
        styler.copyStyles(mock_plan)
        assert styler._numDistricts == 5
        mock_plan.assignLayer.renderer.assert_called_once()
        mock_plan.distLayer.renderer.assert_called_once()
        mock_plan.distLayer.labeling.assert_called_once()

    def test_copy_styles_fewer_districts_no_change(self, mock_planmanager, mock_plan):
        styler = PlanStylerService(mock_planmanager)
        styler._numDistricts = 7
        styler.copyStyles(mock_plan)
        assert styler._numDistricts == 7
        mock_plan.assignLayer.renderer.assert_not_called()
        mock_plan.distLayer.renderer.assert_not_called()
        mock_plan.distLayer.labeling.assert_not_called()

    def test_copy_styles_labeling_not_enabled(self, mock_planmanager, mock_plan, mocker):
        styler = PlanStylerService(mock_planmanager)
        createLabels = mocker.patch.object(styler, "createLabels")
        styler.copyStyles(mock_plan)
        createLabels.assert_not_called()

        styler.clear()
        createLabels.reset_mock()
        mock_plan.distLayer.labelsEnabled.return_value = False
        styler.copyStyles(mock_plan)
        createLabels.assert_called_once()

    def test_create_renderers(self, mock_planmanager):
        styler = PlanStylerService(mock_planmanager)
        styler.createRenderers(5)
        assert styler._ramp is not None
        assert styler._ramp.count() == 6
        assert isinstance(styler._assignRenderer, QgsCategorizedSymbolRenderer)
        assert len(styler._assignRenderer.categories()) == 6
        assert isinstance(styler._distRenderer, QgsCategorizedSymbolRenderer)
        assert len(styler._distRenderer.categories()) == 6

        assignCats = styler._assignRenderer.categories()
        distCats = styler._distRenderer.categories()
        assert assignCats[styler._assignRenderer.categoryIndexForValue(None)].symbol().symbolLayer(0).fillColor() == \
            distCats[styler._distRenderer.categoryIndexForValue(None)].symbol().symbolLayer(0).fillColor()
        assert assignCats[styler._assignRenderer.categoryIndexForValue(1)].symbol().symbolLayer(0).fillColor() == \
            distCats[styler._distRenderer.categoryIndexForValue(1)].symbol().symbolLayer(0).fillColor()
        assert assignCats[styler._assignRenderer.categoryIndexForValue(2)].symbol().symbolLayer(0).fillColor() == \
            distCats[styler._distRenderer.categoryIndexForValue(2)].symbol().symbolLayer(0).fillColor()
        assert assignCats[styler._assignRenderer.categoryIndexForValue(3)].symbol().symbolLayer(0).fillColor() == \
            distCats[styler._distRenderer.categoryIndexForValue(3)].symbol().symbolLayer(0).fillColor()
        assert assignCats[styler._assignRenderer.categoryIndexForValue(4)].symbol().symbolLayer(0).fillColor() == \
            distCats[styler._distRenderer.categoryIndexForValue(4)].symbol().symbolLayer(0).fillColor()
        assert assignCats[styler._assignRenderer.categoryIndexForValue(5)].symbol().symbolLayer(0).fillColor() == \
            distCats[styler._distRenderer.categoryIndexForValue(5)].symbol().symbolLayer(0).fillColor()

        sym = assignCats[0].symbol()
        assert sym.symbolLayer(0).fillColor() == QColor("#c8cfc9")
        sym = assignCats[1].symbol()
        assert sym.symbolLayer(0).fillColor() == styler._ramp.color(1/6)

        sym = distCats[1].symbol()
        assert sym.symbolLayerCount() == 2
        assert isinstance(sym.symbolLayer(0), QgsSimpleFillSymbolLayer)
        assert isinstance(sym.symbolLayer(1), QgsSimpleLineSymbolLayer)

    def test_create_renderers_new_ramp(self, mock_planmanager):
        styler = PlanStylerService(mock_planmanager)
        styler.createRenderers(5)
        ramp0 = styler._ramp
        assert ramp0.count() == 6
        styler.createRenderers(6)
        ramp1 = styler._ramp
        assert ramp1.count() == 7
        assert ramp1.color(1/6) == ramp0.color(1/5)
        assert ramp1.color(2/6) == ramp0.color(2/5)
        assert ramp1.color(3/6) == ramp0.color(3/5)
        assert ramp1.color(4/6) == ramp0.color(4/5)
        assert ramp1.color(5/6) == ramp0.color(1)

    def test_create_labels(self, mock_planmanager):
        styler = PlanStylerService(mock_planmanager)
        styler.createLabels()
        assert styler._labeling is not None
        assert styler._labeling.settings().fieldName == "name"

    def test_style_plan(self, mock_planmanager, mock_plan):
        styler = PlanStylerService(mock_planmanager)
        styler.stylePlan(mock_plan)
        assert styler._numDistricts == 5
        mock_plan.assignLayer.setRenderer.assert_called_once()
        mock_plan.distLayer.setRenderer.assert_called_once()
        mock_plan.distLayer.setLabelsEnabled.assert_called_once()
        mock_plan.distLayer.setLabeling.assert_called_once()

        renderer: QgsCategorizedSymbolRenderer = mock_plan.assignLayer.setRenderer.call_args.args[0]
        assert len(renderer.categories()) == 6

    def test_style_plan_existing_renderer(self, mock_planmanager, mock_plan):
        styler = PlanStylerService(mock_planmanager)
        styler.createRenderers(7)
        styler.stylePlan(mock_plan)
        assert styler._numDistricts == 7
        assert len(styler._assignRenderer.categories()) == 8
        mock_plan.assignLayer.setRenderer.assert_called_once()
        mock_plan.distLayer.setRenderer.assert_called_once()
        mock_plan.distLayer.setLabelsEnabled.assert_called_once()
        mock_plan.distLayer.setLabeling.assert_called_once()

        renderer: QgsCategorizedSymbolRenderer = mock_plan.assignLayer.setRenderer.call_args.args[0]
        assert len(renderer.categories()) == 6

    def test_style_plan_existing_renderer_with_fewer_districts(self, mock_planmanager, mock_plan):
        styler = PlanStylerService(mock_planmanager)
        styler.createRenderers(4)
        assert styler._numDistricts == 4
        assert len(styler._assignRenderer.categories()) == 5
        styler.stylePlan(mock_plan)
        assert styler._numDistricts == 5
        assert len(styler._assignRenderer.categories()) == 6
        mock_plan.assignLayer.setRenderer.assert_called_once()
        mock_plan.distLayer.setRenderer.assert_called_once()
        mock_plan.distLayer.setLabelsEnabled.assert_called_once()
        mock_plan.distLayer.setLabeling.assert_called_once()
