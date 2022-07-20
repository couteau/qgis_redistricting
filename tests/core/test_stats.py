"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class"""


class TestPlanStats:

    def test_create(self, plan):
        stats = plan.stats
        assert stats.cutEdges == 0
        assert stats.avgPolsbyPopper == 0.3533306672318356
        assert stats.avgReock == 0.3907698173405454
        assert stats.avgConvexHull == 0.7834778889302266
        assert stats.cutEdges == 0
        assert len(stats.splits) == 1
