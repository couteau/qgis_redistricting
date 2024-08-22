import pytest

from redistricting.services import PlanBuilder

# pylint: disable=protected-access


class TestCreatePlan:
    @pytest.fixture
    def creator(self, block_layer):
        return PlanBuilder() \
            .setName('test') \
            .setNumDistricts(5) \
            .setGeoLayer(block_layer) \
            .setGeoIdField('geoid') \
            .setPopField('pop_total')

    def test_set_nonexistent_fields_no_validate(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        creator.setPopJoinField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setPopJoinField(None)

        assert creator._validatePopLayer()
        creator.setPopField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setPopField('pop_total')

    def test_append_nonexistent_pop_field_no_validate(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        creator.appendPopField('not_a_field')
        assert not creator._validatePopLayer()

    def test_set_pop_field_updates_districts(self, creator: PlanBuilder):
        creator.appendPopField('vap_total')
        plan = creator.createPlan(createLayers=False)
        assert plan is not None
        assert plan.popFields[0].field == 'vap_total'
        assert hasattr(plan.districts[0], 'vap_total')
