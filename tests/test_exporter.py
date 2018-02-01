import pytest
import mock
from microbenthos.exporters import BaseExporter

class Exporter(BaseExporter):
    _exports_ = 'a'
    __version__ = 'b'

    def prepare(self, sim):
        pass

    def finish(self):
        pass

    def process(self, num, state):
        pass


class TestExporter:

    def test_init(self):
        with pytest.raises(TypeError):
            BaseExporter()
            # abstract base class

        exp = Exporter()

        Exporter._exports_ = ''
        with pytest.raises(ValueError):
            Exporter()

        Exporter._exports_ = 'a'
        Exporter.__version__ = ''
        with pytest.raises(ValueError):
            Exporter()

