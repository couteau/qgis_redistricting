# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - models

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
from .base import lists
from .base.serialization import (
    deserialize,
    serialize
)
from .colors import getColorForDistrict
from .columns import (
    DistrictColumns,
    FieldCategory,
    FieldColors,
    MetricsColumns
)
from .delta import (
    Delta,
    DeltaList
)
from .district import (
    DistrictList,
    RdsDistrict,
    RdsUnassigned
)
from .field import (
    RdsDataField,
    RdsField,
    RdsGeoField,
    RdsRelatedField
)
from .metricslist import (
    MetricTriggers,
    RdsMetric,
    RdsMetrics,
    base_metrics,
    metrics_classes,
    register_metrics
)
from .plan import (
    DeviationType,
    RdsPlan
)
from .splits import (
    RdsSplitBase,
    RdsSplitDistrict,
    RdsSplitGeography,
    RdsSplits
)
from .validators import (
    BaseDeviationValidator,
    MaxDeviationValidator,
    PlusMinusDeviationValidator
)
from .viewmodels import (
    DeltaFieldFilterProxy,
    DeltaListModel,
    DistrictSelectModel,
    GeoFieldsModel,
    PopFieldsModel,
    RdsDistrictDataModel,
    RdsDistrictFilterFieldsProxyModel,
    RdsMetricsModel,
    RdsSplitsModel,
    SourceDistrictModel,
    TargetDistrictModel
)

__all__ = (
    'getColorForDistrict',
    'DeviationType',
    'DistrictColumns',
    'MetricsColumns',
    'FieldCategory',
    'FieldColors',
    'RdsField',
    'RdsGeoField',
    'RdsRelatedField',
    'RdsDataField',
    'GeoFieldsModel',
    'PopFieldsModel',
    'Delta',
    'DeltaList',
    'DeltaListModel',
    'DeltaFieldFilterProxy',
    'BaseDeviationValidator',
    'PlusMinusDeviationValidator',
    'MaxDeviationValidator',
    'RdsDistrict',
    'RdsUnassigned',
    'DistrictList',
    'RdsDistrictDataModel',
    'RdsDistrictFilterFieldsProxyModel',
    'DistrictSelectModel',
    'SourceDistrictModel',
    'TargetDistrictModel',
    'RdsMetric',
    'RdsMetrics',
    'RdsMetricsModel',
    'RdsSplits',
    'RdsSplitBase',
    'RdsSplitDistrict',
    'RdsSplitGeography',
    'RdsSplitsModel',
    'RdsPlan',
    "serialize",
    "deserialize",
    "base_metrics",
    "metrics_classes",
    "register_metrics",
    "MetricTriggers",
)
