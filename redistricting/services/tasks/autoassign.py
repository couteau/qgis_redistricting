"""QGIS Redistricting Plugin - background task to autoassign unassigned geography

        begin                : 2025-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Stuart C. Naifeh
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

from typing import NamedTuple

import geopandas as gpd

try:
    import libpysal

    AUTOASSIGN_ENABLED = True
except ImportError:
    AUTOASSIGN_ENABLED = False

from qgis.core import QgsTask, QgsVectorLayer

from ...errors import CanceledError
from ...utils import LayerReader, SqlAccess, tr
from ._debug import debug_thread


class Row(NamedTuple):
    fid: int
    geoid: str
    district: int
    geometry: str = None


class AutoAssignUnassignedUnits(SqlAccess, QgsTask):
    def __init__(self, assignments: QgsVectorLayer, distField: str):
        super().__init__(tr("Auto assign unassigned units"))
        self.assignments = assignments
        self.distField = distField
        self.distIndex = assignments.fields().lookupField(self.distField)
        if self.distIndex == -1:
            raise ValueError("Invalid district field")
        self.update: dict[int, int] = None
        self.indeterminate: list[Row] = None
        self.retry: list[Row] = None
        self.exception: Exception = None

    def run(self):
        debug_thread()

        try:
            reader = LayerReader(self.assignments, self)
            assignments = (
                reader.read_layer(
                    columns=["fid", "geoid", self.distField],
                    read_geometry=True,
                    fid_as_index=True,
                )
                .reset_index()
                .rename(columns={self.distField: "district"})
            )
            unassigned = assignments[assignments["distrct"] == 0]
            assigned = assignments[assignments["distrct"] != 0]

            # group Rook-adjacent unassigned units
            weights = libpysal.weights.Rook.from_dataframe(unassigned, use_index=False)
            unassigned = unassigned[["fid", "geometry"]].dissolve(by=weights.component_labels, aggfunc=list)
            unassigned["area_geom"] = unassigned.geometry

            unassigned = (
                gpd.sjoin(assigned[["district", "geometry"]], unassigned, predicate="touches")
                .rename(columns={"index_right": "group", "fid_right": "fids"})
                .dissolve(by=["group", "district"])
            )
            # TODO: potentially use amount of the cluster bordered by each district
            #       to determine which district to assign
            unassigned["length"] = unassigned.geometry.intersection(unassigned["area_geom"]).length
            unassigned = (
                unassigned.drop(columns=["geometry", "area_geom"])  # drop the geometry columns
                .drop(unassigned[unassigned["length"] == 0].index)  # drop districts that are only connected by a point
                .reset_index()
                .groupby("group")
                .agg({"district": list, "length": list, "fids": "first"})
            )

            update: dict[int, dict[int, int]] = {}
            indeterminate: list[dict[int, tuple[list, list, list]]] = []
            for group, district, length, fids in unassigned.itertuples(index=True):
                if len(district) == 1:
                    # if the poygon grouping only borders one other district, we can automatically assign
                    update.update({f: {self.distIndex: district[0]} for f in fids})
                else:
                    # if the grouping borders more than one district, we don't automatically assign
                    indeterminate.extend({group: (district, length, fids)})

            self.assignments.dataProvider().changeAttributeValues(update)

            self.update = update
            self.indeterminate = indeterminate
        except CanceledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True

    def finished(self, result):
        if not result:
            return

        if self.update:
            i = self.assignments.fields().indexFromName(self.distField)
            self.assignments.startEditing()
            self.assignments.beginEditCommand("Auto-assign")
            for fid, dist in self.update.items():
                self.assignments.changeAttributeValue(fid, i, dist, 0)
            self.assignments.endEditCommand()
