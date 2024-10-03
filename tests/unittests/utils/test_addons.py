import pathlib
import shutil
import sys

import pytest

import redistricting


# pylint: disable=import-outside-toplevel
class TestAddons:
    @pytest.fixture
    def vendor_dir(self):
        d = pathlib.Path(redistricting.__file__).parent / "vendor"
        yield d

        if d.exists():
            shutil.rmtree(d)

    def test_install_pyogrio(self, vendor_dir):
        from redistricting.utils import addons

        assert not vendor_dir.exists()

        addons.install_pyogrio()

        assert (vendor_dir / 'geopandas').exists()
        assert (vendor_dir / 'pyogrio').exists()
        assert 'geopandas' in sys.modules
        assert sys.modules['geopandas'].__spec__.origin == str(vendor_dir / 'geopandas' / '__init__.py')

    def test_install_pyarrow(self, vendor_dir):
        from redistricting.utils import addons

        assert not vendor_dir.exists()

        addons.install_pyarrow()

        assert (vendor_dir / 'pyarrow').exists()
        assert 'pyarrow' in sys.modules
        assert sys.modules['pyarrow'].__spec__.origin == str(vendor_dir / 'pyarrow' / '__init__.py')

    def test_install_gerrychain(self, vendor_dir):
        from redistricting.utils import addons

        assert not vendor_dir.exists()

        addons.install_gerrychain()

        assert (vendor_dir / 'gerrychain').exists()
        assert 'gerrychain' in sys.modules
        assert sys.modules['gerrychain'].__spec__.origin == str(vendor_dir / 'gerrychain' / '__init__.py')
