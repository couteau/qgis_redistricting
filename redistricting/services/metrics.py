"""QGIS Redistricting Plugin - service for managing metrics updates

        begin                : 2025-08-12
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Cryptodira
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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

import geopandas as gpd
import pandas as pd
from qgis.core import QgsTask
from qgis.PyQt.QtCore import QObject

from ..models.metricslist import MetricLevel, MetricTriggers, get_batches
from ..utils import camel_to_snake, tr
from .districtio import DistrictReader
from .updateservice import UpdateParams, UpdateService, UpdateStatus

if TYPE_CHECKING:
    from ..models import RdsMetrics, RdsPlan


@dataclass
class MetricsUpdate(UpdateParams):
    trigger: "MetricTriggers"
    populationData: Optional[pd.DataFrame]
    districtData: Optional[pd.DataFrame]
    geometry: Optional[gpd.GeoSeries]


class MetricsService(UpdateService):
    paramsCls = MetricsUpdate

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(tr("Calculating district metrics"), parent)

    def _get_batches_for_trigger(self, metrics: "RdsMetrics", trigger: MetricTriggers):
        triggered_metrics = {name: metric for name, metric in metrics.metrics.items() if metric.triggers() & trigger}
        # get all dependencies of the triggered metrics that are not themselves triggered
        #  -- and treat them as satisfied/up-to-date
        ready = {m.name(): m for metric in metrics for m in metric.depends() if not m.triggers() & trigger}

        return get_batches(triggered_metrics, ready)

    def run(self, task: QgsTask, plan: "RdsPlan", params: MetricsUpdate):
        if params.populationData is None:
            params.populationData = self._loadAssignments(plan, True, True, False, task)

        batches = self._get_batches_for_trigger(plan.metrics, params.trigger)
        total = sum(len(b) for b in batches)
        count = 0
        task.setProgress(0)
        for b in batches:
            for metric in b:
                if params.trigger & metric.triggers():
                    depends = {
                        m.name(): plan.metrics[m.name()].value
                        for m in metric.depends()
                        if plan.metrics.metrics.has(m.name())
                    }
                    metric.calculate(params.populationData, params.districtData, params.geometry, plan, **depends)

                count += 1
                task.setProgress(count / total)

        return params

    def _saveDistrictMetrics(self, plan: "RdsPlan", update: MetricsUpdate):
        """updates the district-level metrics in the plan's district layer"""

        def to_dict(value: Union[Mapping, pd.Series, pd.DataFrame]) -> dict:
            if isinstance(value, pd.Series):
                return value.to_dict()
            if isinstance(value, pd.DataFrame):
                return value.to_dict(orient="records")
            if isinstance(value, Mapping):
                return value

            raise TypeError("Unsupported type for serialization.")

        provider = plan.distLayer.dataProvider() if plan.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        dist_metrics: dict[str, Union[Mapping, pd.Series, pd.DataFrame]] = {
            provider.fieldNameIndex(camel_to_snake(m.name())): to_dict(m.value)
            for m in plan.metrics  # pylint: disable=no-member
            if m.level() == MetricLevel.DISTRICT  # only update district level metrics
            and m.serialize()  # only update metrics that are meant to be serialized
            and m.triggers() & update.trigger  # only update if the metric is triggered
            and m.value is not None  # only update if the metric has a value
            # only update if the metric has a corresponding field in the district layer
            and provider.fieldNameIndex(camel_to_snake(m.name())) != -1
        }

        try:
            provider.changeAttributeValues(
                {
                    f.id(): {name: values.get(f[plan.distField]) for name, values in dist_metrics.items()}
                    for f in provider.getFeatures()
                }
            )  # reset the attributes

            plan.distLayer.reload()
            reader = DistrictReader(plan.distLayer, plan.distField, plan.popField, plan.districtColumns)
            reader.loadDistricts(plan)
        except Exception as e:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to update district metrics: {e}") from e

    def finished(
        self,
        status: UpdateStatus,
        task: Optional[QgsTask],
        plan: Optional["RdsPlan"],
        params: Optional[MetricsUpdate],
        exception: Optional[Exception],
    ):
        if status == UpdateStatus.SUCCESS:
            try:
                # Finish metrics calculations
                batches = self._get_batches_for_trigger(plan.metrics, params.trigger)
                update_districts = False

                for b in batches:
                    for metric in b:
                        if metric.level() == MetricLevel.DISTRICT:
                            update_districts = True
                        metric.finished(plan)
                if update_districts:
                    self._saveDistrictMetrics(plan, params)
            except Exception as e:
                exception = e
                status = UpdateStatus.ERROR

        super().finished(status, task, plan, params, exception)

    def update(  # noqa: PLR0913
        self,
        plan: "RdsPlan",
        force: bool = False,
        *,
        trigger: "MetricTriggers",
        populationData: Optional[pd.DataFrame],
        districtData: Optional[pd.DataFrame],
        geometry: Optional[gpd.GeoSeries],
    ):
        return super().update(
            plan, force, trigger=trigger, populationData=populationData, districtData=districtData, geometry=geometry
        )
