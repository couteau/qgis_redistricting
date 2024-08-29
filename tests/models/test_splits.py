import pandas as pd
import pytest

from redistricting.models import (
    RdsGeoField,
    RdsSplitDistrict,
    RdsSplitGeography,
    RdsSplits
)


class TestSplits:
    @pytest.fixture
    def geo_field(self, block_layer):
        return RdsGeoField(block_layer, 'vtdid', 'VTD')

    def test_create_splits(self, geo_field):

        s = RdsSplits(geo_field)
        assert s.geoField == geo_field
        assert s.field == 'vtdid'
        assert s.data is None
