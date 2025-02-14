
from typing import NamedTuple

from qgis.core import (
    QgsTask,
    QgsVectorLayer
)

from ... import CanceledError
from ...utils import (
    LayerReader,
    SqlAccess,
    tr
)
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
        self.update: dict[int, int] = None
        self.indeterminate: list[Row] = None
        self.retry: list[Row] = None
        self.exception: Exception = None

    def run(self):
        debug_thread()

        try:
            reader = LayerReader(self.assignments, self)
            missing = reader.read_layer(columns=["fid", "geoid", self.distField],
                                        filt={self.distField: 0}, read_geometry=True, fid_as_index=True) \
                .reset_index() \
                .rename(columns={self.distField: "district"})

            if len(missing) == self.assignments.featureCount():
                # No units are assigned -- don't waste our time
                raise RuntimeError("Can't infer districts for unassigned units when no units are assigned")

            # find polygons that are adjacent by more than a point
            sql = f"""SELECT fid, geoid, {self.distField} AS district FROM assignments
                        WHERE ST_relate(geometry, GeomFromText(:geometry), 'F***1****')
                            AND fid IN (
                                SELECT id FROM rtree_assignments_geometry r
                                    WHERE r.minx < st_maxx(GeomFromText(:geometry))
                                        AND r.maxx >= st_minx(GeomFromText(:geometry))
                                        AND r.miny < st_maxy(GeomFromText(:geometry))
                                        AND r.maxy >= st_miny(GeomFromText(:geometry))
                                )"""

            with self._connectSqlOgrSqlite(self.assignments.dataProvider()) as db:
                db.row_factory = lambda c, r: Row(*r)
                update: dict[int, int] = {}
                retry: list[Row] = []
                indeterminate: list[Row] = []
                count = 0
                total = len(missing)
                for g in missing.to_wkt().itertuples(index=False, name="Row"):
                    neighbors: list[Row] = db.execute(sql, (g.geometry,)).fetchall()
                    dists = set(r.district for r in neighbors)

                    # is the unassigned unit surrounded by units from the same district or
                    # unassigned units (but not entirely by unassigned units)
                    if len(dists) == 1 and 0 in dists:
                        retry.append(g)
                    elif len(dists) == 1 or (len(dists) == 2 and 0 in dists):
                        newdist = max(dists)
                        if g.fid in update:
                            print("oops")
                        update[g.fid] = newdist
                    else:
                        # multiple adjacent districts
                        indeterminate.append(g)

                    if self.isCanceled():
                        raise CanceledError()

                    count += 1
                    self.setProgress(count/total)

                # TODO: there's probably a better way to to find the surrounding assigned units than continually looping
                while retry:
                    retry_count = len(retry)
                    newretry: list[Row] = []
                    for g in retry:
                        neighbors: list[Row] = db.execute(sql, (g.geometry,)).fetchall()
                        dists = set(update.get(r.fid, r.district) for r in neighbors)

                        # is the unassigned unit surrounded by units from the same district or
                        # unassigned units (but not entirely by unassigned units)
                        if len(dists) == 1 and 0 in dists:
                            newretry.append(g)
                        elif len(dists) == 1 or (len(dists) == 2 and 0 in dists):
                            newdist = max(dists)
                            if g.fid in update:
                                print("oops")
                            update[g.fid] = newdist
                        else:
                            # multiple adjacent districts
                            indeterminate.append(g)

                        if self.isCanceled():
                            raise CanceledError()

                    retry = newretry
                    if len(retry) == retry_count:
                        # if we were unable to assign any of the as-yet unassigned units, give up
                        break

                self.update = update
                self.indeterminate = indeterminate
                self.retry = retry
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
