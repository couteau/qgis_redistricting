"""QGIS Redistricting Plugin - unit tests for Storage class"""
import re
import pytest
from qgis.core import QgsProject
from qgis.PyQt.QtXml import QDomDocument
from redistricting.core.Storage import ProjectStorage
from redistricting.core.Plan import RedistrictingPlan

# pylint: disable=no-self-use


class TestStorage:
    @pytest.fixture
    def project_document(self, block_layer, assign_layer, dist_layer) -> QDomDocument:
        doc = QDomDocument('plan')
        doc.setContent(f"""
        <!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
        <qgis saveUser="joe" saveDateTime="2022-05-05T08:25:43" version="3.18.3-Zürich" saveUserFull="Joe Q. User" projectname="">
          <properties>
            <redistricting>
              <redistricting-plan 
                  num-districts="5" 
                  dist-field="district" 
                  cut-edges="0" 
                  geo-id-display="Block" 
                  description="" 
                  total-population="227036" 
                  vap-field="vap_total" 
                  deviation="0" 
                  name="test" 
                  src-id-field="geoid20" 
                  id="a11bb61d-534d-4cbe-acb0-be04a29d3e2f" 
                  pop-field="pop_total" 
                  pop-layer="{block_layer.id()}" 
                  dist-layer="{dist_layer.id()}" 
                  geo-id-field="geoid20" 
                  assign-layer="{assign_layer.id()}" 
                  src-layer="{block_layer.id()}"
              >
                <data-fields>
                  <data-field expression="0" pctbase="2" layer="{block_layer.id()}" field="vap_nh_white" caption="WVAP" sum="1"/>
                  <data-field expression="0" pctbase="2" layer="{block_layer.id()}" field="vap_nh_black" caption="BVAP" sum="1"/>
                  <data-field expression="0" pctbase="2" layer="{block_layer.id()}" field="vap_apblack" caption="APBVAP" sum="1"/>
                </data-fields>
                <geo-fields>
                  <geo-field expression="0" layer="{assign_layer.id()}" field="vtdid20" caption="VTD"/>
                </geo-fields>
                <districts>
                  <district description="" name="CD1" district="1" members="1"/>
                  <district description="" name="CD2" district="2" members="1"/>
                  <district description="" name="CD3" district="3" members="1"/>
                  <district description="" name="CD4" district="4" members="1"/>
                  <district description="" name="CD5" district="5" members="1"/>
                </districts>
              </redistricting-plan>
              <active-plan>a11bb61d-534d-4cbe-acb0-be04a29d3e2f</active-plan>
            </redistricting>
          </properties>
        </qgis>
        """.encode('utf-8'))
        return doc

    @pytest.fixture
    def empty_project_document(self) -> QDomDocument:
        doc = QDomDocument('plan')
        doc.setContent("""
            <!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
            <qgis saveUser="joe" saveDateTime="2022-05-05T08:25:43" version="3.18.3-Zürich" saveUserFull="Joe Q. User" projectname="">
                <properties>
                </properties>
            </qgis>""".encode('utf-8'))
        return doc

    @pytest.fixture
    def storage(self, project_document) -> ProjectStorage:
        return ProjectStorage(QgsProject.instance(), project_document)

    @pytest.fixture
    def empty_storage(self, empty_project_document) -> ProjectStorage:
        return ProjectStorage(QgsProject.instance(), empty_project_document)

    def test_read_plans(self, storage: ProjectStorage, block_layer, assign_layer, dist_layer):
        plans = storage.readRedistrictingPlans()
        assert len(plans) == 1
        plan = plans[0]
        assert plan.name == 'test'
        assert plan.numDistricts == 5
        assert plan.numSeats == 5
        assert plan.popLayer == block_layer
        assert plan.assignLayer == assign_layer
        assert plan.distLayer == dist_layer
        assert len(plan.districts) == 6
        assert len(plan.dataFields) == 3 and plan.dataFields[0].layer == block_layer
        assert len(plan.geoFields) == 1 and plan.geoFields[0].layer == assign_layer

    def test_read_active_plan(self, storage: ProjectStorage):
        u = storage.readActivePlan()
        assert str(u) == "a11bb61d-534d-4cbe-acb0-be04a29d3e2f"

    def test_write_plan(self,
                        empty_project_document: QDomDocument,
                        empty_storage: ProjectStorage,
                        plan: RedistrictingPlan,
                        dist_layer
                        ):
        empty_storage.writePlan(plan)
        assert re.search(
            f'<redistricting>\\s+<redistricting-plan.+dist-layer="{dist_layer.id()}"',
            empty_project_document.toString()
        )

    def test_write_active_plan(self, empty_storage: ProjectStorage, empty_project_document: QDomDocument, plan):
        empty_storage.writeActivePlan(plan)
        assert re.search(
            f'<redistricting>\\s+<active-plan>{str(plan.id)}</active-plan>',
            empty_project_document.toString()
        )
