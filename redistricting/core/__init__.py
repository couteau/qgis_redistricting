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
from .Plan import RedistrictingPlan
from .utils import makeFieldName, tr, spatialite_connect, createGeoPackage, createGpkgTable, showHelp
from .storage import ProjectStorage
from .District import BaseDistrict, District
from .DistrictList import DistrictList
from .Field import Field, DataField, BasePopulation
from .FieldList import FieldList
from .PlanStats import PlanStatistics
from .PlanStyle import PlanStyler
from .PlanAssignments import PlanAssignmentEditor
from .DistrictDataModel import DistrictDataModel
from .GeoFieldsModel import GeoFieldsModel
from .DeltaListModel import DeltaListModel
from .PlanBuilder import PlanBuilder
from .PlanEdit import PlanEditor
from .PlanExport import PlanExporter
from .PlanImport import AssignmentImporter, ShapefileImporter
from .PlanCopy import PlanCopier
from .Exception import RdsException

__all__ = ['RedistrictingPlan', 'PlanBuilder', 'PlanEditor', 'ProjectStorage',
           'BaseDistrict', 'District', 'DistrictList', 'FieldList', 'Field', 'DataField',
           'BasePopulation', 'DistrictDataModel', 'GeoFieldsModel', 'DeltaListModel',
           'PlanAssignmentEditor', 'PlanExporter', 'AssignmentImporter', 'ShapefileImporter',
           'PlanCopier', 'PlanStyler',
           'makeFieldName', 'tr', 'spatialite_connect', 'createGeoPackage', 'createGpkgTable',
           'showHelp', 'RdsException', 'PlanStatistics']
