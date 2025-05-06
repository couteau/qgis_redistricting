"""QGIS Redistricting Plugin - unit tests for RdsMetrics classes

Copyright (C) 2025, Stuart C. Naifeh

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

from redistricting.models import metrics, metricslist


class TestMetrics:
    def test_metrics_definitions(self):
        assert metrics.RdsTotalPopulationMetric.get_type() is int
        assert metrics.RdsTotalPopulationMetric.name() == "totalPopulation"

    def test_define_metric(self, mock_plan):
        class TestMetricClass(metricslist.RdsMetric[str], mname="test"):
            def calculate(self, populationData, geometry, plan, **depends):
                self._value = "dummy"

        m = TestMetricClass()
        m.calculate(None, None, mock_plan)
        assert m.value == "dummy"
