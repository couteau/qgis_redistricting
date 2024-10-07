from redistricting.models import District
from redistricting.services.DistrictIO import DistrictReader


class TestDistrictReader:
    def test_readdistricts(self, dist_layer):
        r = DistrictReader(dist_layer)
        l = r.readFromLayer()
        assert len(l) == 5
        assert all(isinstance(d, District) for d in l)
