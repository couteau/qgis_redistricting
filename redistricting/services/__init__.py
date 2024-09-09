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
from .actions import ActionRegistry
from .clipboard import DistrictClipboardAccess
from .DeltaListModel import DeltaListModel
from .DeltaUpdate import DeltaUpdateService
from .DistrictCopy import DistrictCopier
from .DistrictDataModel import RdsDistrictDataModel
from .DistrictModels import (
    DistrictSelectModel,
    SourceDistrictModel,
    TargetDistrictModel
)
from .DistrictUpdate import DistrictUpdater
from .DistrictValid import DistrictValidator
from .ErrorList import ErrorListMixin
from .FieldListModels import (
    GeoFieldsModel,
    PopFieldsModel
)
from .LayerTreeManager import LayerTreeManager
from .MetricsModel import RdsPlanMetricsModel
from .PlanAssignments import (
    AssignmentsService,
    PlanAssignmentEditor
)
from .PlanBuilder import PlanBuilder
from .PlanColors import getColorForDistrict
from .PlanCopy import PlanCopier
from .PlanEdit import PlanEditor
from .PlanExport import PlanExporter
from .PlanImport import (
    AssignmentImporter,
    PlanImportService,
    ShapefileImporter
)
from .PlanListModel import PlanListModel
from .PlanManager import PlanManager
from .PlanStyle import PlanStylerService
from .SplitsModel import RdsSplitsModel
from .storage import ProjectStorage

__all__ = (
    'ActionRegistry', 'PlanManager', 'LayerTreeManager', 'DistrictClipboardAccess',
    'PlanBuilder', 'PlanEditor', 'PlanCopier', 'PlanStylerService',
    'DistrictUpdater', 'DeltaUpdateService', 'DistrictValidator',
    'PlanAssignmentEditor', 'AssignmentsService', 'DistrictCopier',
    'PlanExporter', 'AssignmentImporter', 'ShapefileImporter', 'PlanImportService',
    'ProjectStorage', 'ErrorListMixin', 'getColorForDistrict',
    'GeoFieldsModel', 'PopFieldsModel', 'RdsPlanMetricsModel', 'RdsDistrictDataModel', 'DeltaListModel', 'RdsSplitsModel',
    'DistrictSelectModel', 'TargetDistrictModel', 'SourceDistrictModel', 'PlanListModel'
)
