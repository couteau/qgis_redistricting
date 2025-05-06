"""QGIS Redistricting Plugin - unit tests

Copyright 2022-2025, Stuart C. Naifeh

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

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from redistricting.services.tasks.importequivalency import ImportAssignmentFileTask


class TestImportEquivalencyTask:
    @pytest.fixture
    def assignmentfile_csv(self, datadir: pathlib.Path):
        return datadir / "tuscaloosa_be.csv"

    @pytest.fixture
    def assignmentfile_xlsx(self, datadir: pathlib.Path):
        return datadir / "tuscaloosa_be.xlsx"

    @pytest.fixture
    def assignmentfile_xls(self, datadir: pathlib.Path):
        return datadir / "tuscaloosa_be.xls"

    @pytest.fixture
    def assignmentfile_ods(self, datadir: pathlib.Path):
        return datadir / "tuscaloosa_be.ods"

    @pytest.fixture
    def assignmentfile_fwf(self, datadir: pathlib.Path):
        return datadir / "tuscaloosa_be.txt"

    def test_import_equivalency_csv(self, plan, assignmentfile_csv, mocker: MockerFixture):
        task = ImportAssignmentFileTask(plan, assignmentfile_csv, geoColumn="geoid20", distColumn="district")
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert result
        assert progress.call_count == 6567
        progress.assert_called_with(100)

    def test_import_equivalency_csv_vtd(self, plan, datadir: pathlib.Path, mocker: MockerFixture):
        task = ImportAssignmentFileTask(
            plan,
            (datadir / "tuscaloosa_ve.csv").resolve(),
            geoColumn="vtdid20",
            distColumn="district",
            joinField="vtdid",
        )
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert result
        assert progress.call_count == 54
        progress.assert_called_with(100)

    def test_import_equivalency_non_existent_file_sets_error_and_returns_false(
        self, plan, datadir: pathlib.Path, mocker: MockerFixture
    ):
        task = ImportAssignmentFileTask(
            plan,
            (datadir / "nofile.csv").resolve(),
            geoColumn="geoid20",
            distColumn="district",
        )
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert not result
        assert task.exception is not None
        assert isinstance(task.exception, FileNotFoundError)
        progress.assert_not_called()

    def test_import_equivalency_bad_delimiter_sets_error_and_returns_false(
        self, plan, assignmentfile_csv: pathlib.Path, mocker: MockerFixture
    ):
        task = ImportAssignmentFileTask(
            plan, assignmentfile_csv, geoColumn="geoid20", distColumn="district", delimiter="&"
        )
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert not result
        assert task.exception is not None
        assert isinstance(task.exception, ValueError)
        progress.assert_not_called()

    def test_import_equivalency_emptyfile_sets_error_and_returns_false(
        self, plan, datadir: pathlib.Path, mocker: MockerFixture
    ):
        (datadir / "empty.csv").touch()
        task = ImportAssignmentFileTask(
            plan, datadir / "empty.csv", geoColumn="geoid20", distColumn="district", delimiter="&"
        )
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert not result
        assert task.exception is not None
        assert isinstance(task.exception, pd.errors.EmptyDataError)
        progress.assert_not_called()

    def test_import_equivalency_xlsx(self, plan, assignmentfile_xlsx, mocker: MockerFixture):
        task = ImportAssignmentFileTask(plan, assignmentfile_xlsx, geoColumn="geoid20", distColumn="district")
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert result
        assert progress.call_count == 6567
        progress.assert_called_with(100)

    def test_import_equivalency_xls(self, plan, assignmentfile_xls, mocker: MockerFixture):
        task = ImportAssignmentFileTask(plan, assignmentfile_xls, geoColumn="geoid20", distColumn="district")
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert result
        assert progress.call_count == 6567
        progress.assert_called_with(100)

    def test_import_equivalency_ods(self, plan, assignmentfile_ods, mocker: MockerFixture):
        task = ImportAssignmentFileTask(plan, assignmentfile_ods, geoColumn="geoid20", distColumn="district")
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert result
        assert progress.call_count == 6567
        progress.assert_called_with(100)

    def test_import_equivalency_fwf(self, plan, assignmentfile_fwf, mocker: MockerFixture):
        task = ImportAssignmentFileTask(plan, assignmentfile_fwf, headerRow=False, delimiter=" ")
        progress = mocker.patch.object(task, "setProgress")
        result = task.run()
        assert result
        assert progress.call_count == 6567
        progress.assert_called_with(100)
