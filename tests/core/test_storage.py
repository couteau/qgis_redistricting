"""QGIS Redistricting Plugin - unit tests for Storage class

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
import re
import pytest
from qgis.core import QgsProject
from qgis.PyQt.QtXml import QDomDocument
from redistricting.core.storage import ProjectStorage
from redistricting.core.Plan import RedistrictingPlan


class TestStorage:
    @pytest.fixture
    def project_document(self, block_layer, assign_layer, dist_layer) -> QDomDocument:
        doc = QDomDocument('plan')
        doc.setContent(f"""
            <!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'>
            <qgis version="3.18.3-Zürich" projectname="" saveUser="joe" saveUserFull="Joe Q. User" saveDateTime="2022-05-05T08:25:43">
                <properties>
                    <redistricting version="1.0.0">
                        <redistricting-plan name="test" uuid="a11bb61d-534d-4cbe-acb0-be04a29d3e2f">
                            <![CDATA[{{"id": "a11bb61d-534d-4cbe-acb0-be04a29d3e2f", 
                            "name": "test", 
                            "description": "", 
                            "total-population": 227036, 
                            "num-districts": 5, 
                            "deviation": 0.025, 
                            "pop-layer": "{block_layer.id()}", 
                            "assign-layer": "{assign_layer.id()}", 
                            "dist-layer": "{dist_layer.id()}", 
                            "geo-id-field": "geoid20", 
                            "geo-id-display": "", 
                            "dist-field": "district", 
                            "pop-field": "pop_total", 
                            "vap-field": "vap_total", 
                            "data-fields": [
                                {{
                                    "layer": "{block_layer.id()}", 
                                    "field": "vap_apblack", 
                                    "expression": false, 
                                    "caption": "APBVAP", 
                                    "sum": true, 
                                    "pctbase": 2
                                }}, 
                                {{
                                    "layer": "{block_layer.id()}", 
                                    "field": "vap_nh_white", 
                                    "expression": false, 
                                    "caption": "WVAP", 
                                    "sum": true, 
                                    "pctbase": 2
                                }}, 
                                {{
                                    "layer": "{block_layer.id()}", 
                                    "field": "vap_hispanic", 
                                    "expression": false, 
                                    "caption": "HVAP", 
                                    "sum": true, 
                                    "pctbase": 2
                                }}
                            ], 
                            "geo-fields": [
                                {{
                                    "layer": "{assign_layer.id()}", 
                                    "field": "vtdid20", 
                                    "expression": false, 
                                    "caption": "VTD"
                                }}
                            ], 
                            "districts": [
                                {{
                                    "district": 1, 
                                    "name": "CD1", 
                                    "members": 1
                                }}, 
                                {{
                                    "district": 2, 
                                    "name": "CD2", 
                                    "members": 1
                                }},
                                {{
                                    "district": 3, 
                                    "name": "CD3", 
                                    "members": 1
                                }}, 
                                {{
                                    "district": 4, 
                                    "name": "CD4", 
                                    "members": 1
                                }}, 
                                {{
                                    "district": 5, 
                                    "name": "CD5", 
                                    "members": 1
                                }}
                            ], 
                            "plan-stats": {{
                                "cut-edges": 0, 
                                "splits": {{
                                    "vtdid20": []
                                }}
                            }}}}]]>
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

    def test_write_plan(
        self,
        empty_project_document: QDomDocument,
        empty_storage: ProjectStorage,
        plan: RedistrictingPlan,
        dist_layer,
        block_layer
    ):
        empty_storage.writePlan(plan)
        assert re.search(
            '<redistricting version="1.0.0">\\s*<redistricting-plan\\s+'
            '(?=.*\\bname\\b)(?=.*\\bid\\b).*><!\\[CDATA\\[\\{'
            f'(?=.*"dist-layer":\\s*"{dist_layer.id()}")'
            f'(?=.*"pop-layer":\\s*"{block_layer.id()}")'
            '.*\\}\\]\\]>\\s*</redistricting-plan>\\s*</redistricting>',
            empty_project_document.toString()
        )

    def test_write_active_plan(self, empty_storage: ProjectStorage, empty_project_document: QDomDocument, plan):
        empty_storage.writeActivePlan(plan)
        assert re.search(
            f'<redistricting version="1.0.0">\\s+<active-plan>{str(plan.id)}</active-plan>',
            empty_project_document.toString()
        )
