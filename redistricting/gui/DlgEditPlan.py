# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - New/Edit Plan Dialog

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

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
from qgis.core import (
    QgsProject,
    QgsVectorLayer
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QWizard
from qgis.utils import iface

from ..core import (
    FieldList,
    RedistrictingPlan,
    showHelp,
    tr
)
from ._dlgEditPlanDetailsPage import dlgEditPlanDetailsPage
from ._dlgEditPlanFieldPage import dlgEditPlanFieldPage
from ._dlgEditPlanGeoPage import dlgEditPlanGeoPage
from ._dlgEditPlanImportPage import dlgEditPlanImportPage
from ._dlgEditPlanPopPage import dlgEditPlanPopPage
from .RdsFieldComboBox import RdsFieldComboBox
from .RdsFieldTableView import RdsFieldTableView
from .RdsMapLayerComboBox import RdsMapLayerComboBox

iface: QgisInterface


class DlgEditPlan(QWizard):
    plan: RedistrictingPlan = None

    def __init__(self, plan: RedistrictingPlan = None, parent=None, ):
        super().__init__(parent)
        self.new = plan is None
        self.setWindowTitle(
            tr('New Redistricting Plan') if plan is None else
            tr('Edit Redistricting Plan')
        )
        self.setModal(False)
        self.wizardStyle = QWizard.ModernStyle
        self.setOptions(QWizard.NoBackButtonOnStartPage |
                        QWizard.CancelButtonOnLeft |
                        QWizard.NoDefaultButton |
                        QWizard.HaveFinishButtonOnEarlyPages |
                        QWizard.HaveHelpButton |
                        QWizard.HelpButtonOnRight)

        self.setDefaultProperty('RdsMapLayerComboBox', 'layer', RdsMapLayerComboBox.layerChanged)
        self.setDefaultProperty('RdsFieldComboBox', 'field', RdsFieldComboBox.fieldChanged)
        self.setDefaultProperty('RdsFieldTableView', 'fields', RdsFieldTableView.fieldsChanged)

        self.helpRequested.connect(self.showHelp)

        self.addPage(dlgEditPlanDetailsPage(self))
        self.addPage(dlgEditPlanGeoPage(self))
        self.addPage(dlgEditPlanPopPage(self))
        self.addPage(dlgEditPlanFieldPage(self))

        if plan:
            self.setField('planName', plan.name)
            self.setField('description', plan.description)
            self.setField('numDistricts', plan.numDistricts)
            self.setField('numSeats', plan.numSeats)
            self.setField('deviation', plan.deviation * 100)
            self.setField('geoIdField', plan.geoIdField)
            self.setField('geoCaption', plan.geoIdCaption)
            self.setField('gpkgPath', plan.geoPackagePath)
            self.setField('popLayer', plan.popLayer)
            self.setField('joinField', plan.popJoinField)
            self.setField('popField', plan.popField)
            self.setField('sourceLayer', plan.geoLayer)
            self.setField('geoFields', list(plan.geoFields))
            self.setField('popFields', list(plan.popFields))
            self.setField('dataFields', list(plan.dataFields))
        else:
            self.addPage(dlgEditPlanImportPage(self))
            l = iface.activeLayer()
            if not isinstance(l, QgsVectorLayer):
                l = None
                for _, lyr in QgsProject.instance().mapLayers(True).items():
                    if isinstance(lyr, QgsVectorLayer):
                        l = lyr
                        break
            if l is None:
                raise ValueError(tr("No vector layer found in project"))
            
            self.setField('sourceLayer', l)

    def showHelp(self):
        showHelp(f'usage/create_plan.html#page-{self.currentId()+1}')

    def planName(self):
        return self.field('planName')

    def description(self):
        return self.field('description')

    def numDistricts(self):
        return self.field('numDistricts')

    def numSeats(self):
        return self.field('numSeats')

    def sourceLayer(self):
        layer = self.field('sourceLayer')
        return None if isinstance(layer, QVariant) else layer

    def geoIdField(self):
        return self.field('geoIdField')

    def geoIdDisplay(self):
        return self.field('geoCaption')

    def geoFields(self):
        return self.field('geoFields')

    def popLayer(self):
        layer = self.field('popLayer')
        return None if isinstance(layer, QVariant) else layer

    def joinField(self):
        return self.field('joinField') or self.field('geoIdField')

    def popField(self):
        return self.field('popField')

    def deviation(self):
        return self.field('deviation') / 100

    def popFields(self):
        return self.field('popFields')
    
    def dataFields(self):
        return self.field('dataFields')

    def gpkgPath(self):
        return self.field('gpkgPath')

    def importPlan(self):
        return bool(self.field('importPath'))

    def importHeaderRow(self):
        return self.field('headerRow')

    def importPath(self):
        return self.field('importPath')

    def importField(self):
        return self.field('importField')

    def importDelim(self):
        return self.field('delimiter')

    def importQuote(self):
        return self.field('quote')

    def importGeoCol(self):
        return self.field('geoCol') - 1

    def importDistCol(self):
        return self.field('distCol') - 1

    def isComplete(self):
        for pageId in self.pageIds():
            if not self.page(pageId).isComplete():
                return False
        return True

    def updatePlan(self, plan: RedistrictingPlan):
        if not self.isComplete():
            return False
        plan.name = self.field('planName')
        plan.numDistricts = self.field('numDistricts')
        plan.numSeats = self.field('numSeats')
        plan.description = self.field('description')
        plan.geoLayer = self.field('sourceLayer')
        plan.geoIdField = self.field('geoIdField')
        plan.geoIdCaption = self.field('geoCaption')
        plan.geoFields = self.field('geoFields')
        plan.popLayer = self.field('popLayer')
        plan.popField = self.field('popField')
        plan.deviation = self.field('deviation') / 100
        plan.dataFields = self.field('dataFields')
        return True

    def createPlan(self):
        if not self.isComplete():
            return None
        plan = RedistrictingPlan(parent=QgsProject.instance(), name=self.field(
            'planName'), numDistricts=self.field('numDistricts'))
        plan.numSeats = self.field('numSeats')
        plan.description = self.field('description')
        plan.geoLayer = self.field('sourceLayer')
        plan.geoIdField = self.field('geoIdField')
        plan.geoIdCaption = self.field('geoCaption')
        plan.popLayer = self.field('popLayer')
        plan.popField = self.field('popField')
        plan.deviation = self.field('deviation') / 100
        plan.dataFields = self.field('dataFields')
        plan.geoFields = self.field('geoFields')
        return plan
