import pytest
from qgis.PyQt.QtWidgets import QToolBar

from redistricting import services


# pylint: disable=unused-argument, redefined-outer-name
class Fixtures:
    @pytest.fixture
    def planmanager(self, qgis_new_project):
        planManager = services.PlanManager()
        return planManager

    @pytest.fixture
    def layertreemanager(self, qgis_new_project):
        svc = services.LayerTreeManager()
        return svc

    @pytest.fixture
    def styler_service(self, planmanager):
        svc = services.PlanStylerService(planmanager)
        return svc

    @pytest.fixture
    def toolbar(self):  # pylint: disable=unused-argument, redefined-outer-name
        tb = QToolBar("test toolbar")
        return tb

    @pytest.fixture
    def delta_update_service(self):
        svc = services.DeltaUpdateService()
        return svc

    @pytest.fixture
    def assignment_service(self, delta_update_service: services.DeltaUpdateService):  # pylint: disable=redefined-outer-name
        svc = services.AssignmentsService()
        svc.editingStarted.connect(delta_update_service.watchPlan)
        svc.editingStopped.connect(delta_update_service.unwatchPlan)
        return svc

    @pytest.fixture
    def district_update_service(self):
        svc = services.DistrictUpdater()
        return svc

    @pytest.fixture
    def import_service(self, district_update_service: services.DistrictUpdater):
        svc = services.PlanImportService()
        svc.importComplete.connect(lambda plan: district_update_service.updateDistricts(
            plan, needDemographics=True, needGeometry=True, needSplits=True, force=True
        ))
