from pytest_mock import MockerFixture

from redistricting.models import (
    RdsDistrict,
    RdsPlan
)
from redistricting.models.DistrictValid import PlusMinusDeviationValidator


class TestDistrictValidator:
    def test_validate_district(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.05
        v = PlusMinusDeviationValidator(plan)

        district = mocker.create_autospec(spec=RdsDistrict)
        district.members = 1

        district.population = 100
        assert v.validateDistrict(district)

        district.population = 105
        assert v.validateDistrict(district)

        district.population = 95
        assert v.validateDistrict(district)

        district.population = 106
        assert not v.validateDistrict(district)

        district.population = 94
        assert not v.validateDistrict(district)

        plan.deviation = 0
        district.population = 100
        assert v.validateDistrict(district)

    def test_validate_district_multi_member(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RdsPlan)
        plan.totalPopulation = 500
        plan.numDistricts = 5
        plan.numSeats = 5
        plan.deviation = 0.05
        v = PlusMinusDeviationValidator()

        district = mocker.create_autospec(spec=RdsDistrict)
        district.members = 2

        district.population = 200
        assert v.validateDistrict(district)

        district.population = 210
        assert v.validateDistrict(district)

        district.population = 190
        assert v.validateDistrict(district)

        district.population = 211
        assert not v.validateDistrict(district)

        district.population = 189
        assert not v.validateDistrict(district)

        plan.deviation = 0
        district.population = 200
        assert v.validateDistrict(district)
