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
from redistricting.gui import DockRedistrictingToolbox

# pylint: disable=protected-access


class TestDistrictTools:
    def test_create(self, mock_plan, mocker):
        dockwidget = DockRedistrictingToolbox()
        mocker.patch.object(dockwidget, "btnUndo")
        mocker.patch.object(dockwidget, "btnRedo")
        dockwidget.plan = mock_plan
        assert dockwidget.plan is mock_plan
        assert dockwidget.lblPlanName.text() == "test"
        assert dockwidget.cmbGeoSelect.isEnabled()

    def test_set_plan_none_clears_widget(self, mock_plan, mocker):
        dockwidget = DockRedistrictingToolbox()
        mocker.patch.object(dockwidget, "btnUndo")
        mocker.patch.object(dockwidget, "btnRedo")
        dockwidget.plan = mock_plan
        assert dockwidget.plan is mock_plan
        dockwidget.plan = None
        assert dockwidget.plan is None
        assert dockwidget._undoStack is None
        assert dockwidget.lblPlanName.text() == "No plan selected"
        assert not dockwidget.cmbGeoSelect.isEnabled()
