"""QGIS Redistricting Plugin - unit tests for updating changes background task

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
from redistricting.models.Plan import RedistrictingPlan
from redistricting.services.Tasks.UpdatePendingTask import (
    AggregatePendingChangesTask
)


class TestUpdatePendingChangesTask:
    def test_create(self, mock_plan):
        t = AggregatePendingChangesTask(mock_plan)
        assert t.exception is None

    def test_run(self, mock_plan: RedistrictingPlan):
        mock_plan.assignLayer.startEditing()
        f = next(mock_plan.assignLayer.getFeatures())
        i = mock_plan.assignLayer.fields().lookupField(mock_plan.distField)
        mock_plan.assignLayer.changeAttributeValue(f.id(), i, f[i] + 1, f[i])
        t = AggregatePendingChangesTask(mock_plan)
        t.run()
        assert t.data is not None
        assert len(t.data) == 2
