"""QGIS Redistricting Plugin - unit tests for import shape background task

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
import pathlib

from redistricting.services.tasks.importshape import ImportShapeFileTask


class TestImportShapeFileTask:
    def test_import_shapefile(self, plan, datadir: pathlib.Path):
        t = ImportShapeFileTask(plan, str((datadir / "test_plan.shp").resolve()), "district")
        result = t.run()
        assert result
        assert len(t.errors) == 0
