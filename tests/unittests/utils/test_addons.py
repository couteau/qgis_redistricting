import pathlib
import shutil

import pytest
from qgis.PyQt.QtCore import QStandardPaths

import redistricting


# pylint: disable=import-outside-toplevel
class TestAddons:
    @pytest.fixture
    def vendor_dir(self):
        d = pathlib.Path(redistricting.__file__).parent / "vendor"

        yield d

        if d.exists():
            shutil.rmtree(d)

    @pytest.mark.xdist_group("addons")
    def test_install_pyogrio(self, vendor_dir):
        from redistricting.utils import addons

        assert not vendor_dir.exists()

        process = addons.install_pyogrio()
        process.waitForFinished()

        assert (vendor_dir / "pyogrio").exists()
        assert (pathlib.Path(QStandardPaths.standardLocations(QStandardPaths.StandardLocation.AppDataLocation)[0])
                / "startup.py").exists()
        (pathlib.Path(QStandardPaths.standardLocations(
            QStandardPaths.StandardLocation.AppDataLocation)[0]) / "startup.py").unlink()

    @pytest.mark.xdist_group("addons")
    def test_install_pyarrow(self, vendor_dir):
        from redistricting.utils import addons

        assert not vendor_dir.exists()

        process = addons.install_pyarrow()
        process.waitForFinished()

        assert (vendor_dir / "pyarrow").exists()
        assert (pathlib.Path(QStandardPaths.standardLocations(QStandardPaths.StandardLocation.AppDataLocation)[0])
                / "startup.py").exists()
        (pathlib.Path(QStandardPaths.standardLocations(
            QStandardPaths.StandardLocation.AppDataLocation)[0]) / "startup.py").unlink()
