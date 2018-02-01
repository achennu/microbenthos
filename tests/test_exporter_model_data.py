import pytest
from microbenthos.exporters.model_data import ModelDataExporter

class TestModelDataExporter:

    def test_init(self):
        exp = ModelDataExporter()
