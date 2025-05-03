import redistricting.utils.layer


# pylint: disable=import-outside-toplevel
class TestLayerReader:
    def test_readqgis(self, block_layer):
        reader = redistricting.utils.layer.LayerReader(block_layer)
        reader.read_qgis()

    def test_gpd_read(self, block_layer):
        reader = redistricting.utils.layer.LayerReader(block_layer)
        reader.gpd_read(chunksize=-1)
