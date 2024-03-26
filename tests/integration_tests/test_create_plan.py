import pytest

from redistricting.services import PlanBuilder

# pylint: disable=protected-access


class TestCreatePlan:
    def test_set_nonexistent_fields_no_validate(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        creator.setPopJoinField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setPopJoinField(None)

        assert creator._validatePopLayer()
        creator.setPopField('not_a_field')
        assert not creator._validatePopLayer()
        creator.setPopField('pop_total')

    def test_append_nonexistent_field_raises_error(self, creator: PlanBuilder):
        assert creator._validatePopLayer()
        with pytest.raises(ValueError):
            creator.appendPopField('not_a_field')

    def test_set_pop_field_updates_districts(self, creator: PlanBuilder):
        plan = creator.createPlan(createLayers=False)
        assert hasattr(plan.districts[0], 'pop_total')
        assert not plan._updater._needDemographicUpdate

        creator.appendPopField('vap_total')
        plan = creator.createPlan(createLayers=False)
        assert plan.popFields[0].field == 'vap_total'
        assert hasattr(plan.districts[0], 'vap_total')
