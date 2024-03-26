from pytest_mock import MockerFixture

from redistricting.models import (
    District,
    RedistrictingPlan
)
from redistricting.services.DistrictValid import DistrictValidator


class TestDistrictValidator:
    def test_validate_district(self, mocker: MockerFixture):
        v = DistrictValidator()
        plan = mocker.create_autospec(spec=RedistrictingPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.05

        district = mocker.create_autospec(spec=District)
        district.members = 1

        district.population = 100
        assert v.validateDistrict(plan, district)

        district.population = 105
        assert v.validateDistrict(plan, district)

        district.population = 95
        assert v.validateDistrict(plan, district)

        district.population = 106
        assert not v.validateDistrict(plan, district)

        district.population = 94
        assert not v.validateDistrict(plan, district)

        plan.deviation = 0
        district.population = 100
        assert v.validateDistrict(plan, district)

    def test_validate_district_multi_member(self, mocker: MockerFixture):
        v = DistrictValidator()
        plan = mocker.create_autospec(spec=RedistrictingPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.05

        district = mocker.create_autospec(spec=District)
        district.members = 2

        district.population = 200
        assert v.validateDistrict(plan, district)

        district.population = 210
        assert v.validateDistrict(plan, district)

        district.population = 190
        assert v.validateDistrict(plan, district)

        district.population = 211
        assert not v.validateDistrict(plan, district)

        district.population = 189
        assert not v.validateDistrict(plan, district)

        plan.deviation = 0
        district.population = 200
        assert v.validateDistrict(plan, district)
