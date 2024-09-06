import pytest
from qgis.PyQt.QtWidgets import QToolBar

from redistricting import services


class Fixtures:
    @pytest.fixture
    def planmanager(self, patch_iface, qgis_new_project):  # pylint: disable=unused-argument, redefined-outer-name
        planManager = services.PlanManager()
        return planManager

    @pytest.fixture
    def toolbar(self, patch_iface):  # pylint: disable=unused-argument, redefined-outer-name
        tb = QToolBar("test toolbar")
        return tb

    @pytest.fixture
    def update_service(self):
        svc = services.DeltaUpdateService()
        return svc

    @pytest.fixture
    def assignment_service(self, update_service):  # pylint: disable=redefined-outer-name
        svc = services.AssignmentsService(update_service)
        return svc
