# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - core classes

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
from .DeltaListModel import DeltaListModel
from .District import (
    BaseDistrict,
    District
)
from .DistrictDataModel import DistrictDataModel
from .DistrictList import DistrictList
from .Exception import RdsException
from .Field import (
    DataField,
    Field
)
from .FieldList import FieldList
from .FieldListModels import (
    GeoFieldsModel,
    PopFieldsModel
)
from .Plan import RedistrictingPlan
from .PlanAssignments import PlanAssignmentEditor
from .PlanBuilder import PlanBuilder
from .PlanCopy import PlanCopier
from .PlanEdit import PlanEditor
from .PlanExport import PlanExporter
from .PlanImport import (
    AssignmentImporter,
    ShapefileImporter
)
from .PlanStats import PlanStatistics
from .PlanStyle import PlanStyler
from .storage import ProjectStorage
from .utils import (
    createGeoPackage,
    createGpkgTable,
    makeFieldName,
    showHelp,
    spatialite_connect,
    tr
)

__all__ = ['RedistrictingPlan', 'PlanBuilder', 'PlanEditor', 'ProjectStorage',
           'BaseDistrict', 'District', 'DistrictList', 'FieldList', 'Field', 'DataField',
           'DistrictDataModel', 'FieldListModels', 'DeltaListModel',
           'PlanAssignmentEditor', 'PlanExporter', 'AssignmentImporter', 'ShapefileImporter',
           'PlanCopier', 'PlanStyler',
           'makeFieldName', 'tr', 'spatialite_connect', 'createGeoPackage', 'createGpkgTable',
           'showHelp', 'RdsException', 'PlanStatistics',
           'GeoFieldsModel', 'PopFieldsModel']
