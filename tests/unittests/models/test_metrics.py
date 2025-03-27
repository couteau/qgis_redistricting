import redistricting.models.metrics as metrics
import redistricting.models.metricslist as metricslist


class TestMetrics:
    def test_metrics_definitions(self):
        assert metrics.RdsTotalPopulationMetric.get_type() == int
        assert metrics.RdsTotalPopulationMetric.name() == "totalPopulation"

    def test_define_metric(self, mock_plan):
        class TestMetricClass(metricslist.RdsMetric[str], name="test"):
            def calculate(self, populationData, geometry, **depends):
                self._value = "dummy"

        m = TestMetricClass(mock_plan)
        m.calculate(None, None)
        assert m.value() == "dummy"
