from redistricting.models import RdsDistrict
from redistricting.services.DistrictIO import DistrictReader


class TestDistrictReader:
    def test_readdistricts(self, dist_layer):
        r = DistrictReader(dist_layer)
        l = r.readFromLayer()
        assert len(l) == 5
        assert all(isinstance(d, RdsDistrict) for d in l)
