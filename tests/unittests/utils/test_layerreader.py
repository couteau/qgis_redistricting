import functools
import timeit

import redistricting.utils.layer


# pylint: disable=import-outside-toplevel
class TestLayerReader:
    def test_readqgis(self, block_layer):
        reader = redistricting.utils.layer.LayerReader(block_layer)

        t1 = timeit.timeit(reader.read_qgis, number=20)
        print(t1)

    def test_gpd_read(self, block_layer):
        reader = redistricting.utils.layer.LayerReader(block_layer)
        t2 = timeit.timeit(functools.partial(reader.gpd_read, chunksize=-1), number=20)
        print(t2)
