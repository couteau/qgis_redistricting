"""QGIS Redistricting Plugin - unit tests for PlanStats class

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


class TestPlanStats:

    def test_create(self, plan):
        stats = plan.stats
        assert stats.cutEdges == 0
        assert stats.avgPolsbyPopper == 0.3533306672318356
        assert stats.avgReock == 0.3907698173405454
        assert stats.avgConvexHull == 0.7834778889302266
        assert stats.cutEdges == 0
        assert len(stats.splits) == 1
