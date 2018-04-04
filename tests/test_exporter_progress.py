import pytest

from microbenthos.exporters.progress import ProgressExporter


class TestProgressExporter:

    def test_init(self):
        exp = ProgressExporter()
        # check the defaults
        assert exp._total_time is None

    @pytest.mark.xfail(reason='not implemented')
    def test_setup(self):
        exp = ProgressExporter()
        raise NotImplementedError()
        # exp.setup(runner, state)

    @pytest.mark.xfail(reason='Not implemented')
    def test_prepare(self):
        # exporter.prepare(state)
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_process(self):
        # exporter.process(num, state)
        raise NotImplementedError
