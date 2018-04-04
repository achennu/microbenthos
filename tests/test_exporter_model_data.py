import pytest

from microbenthos.exporters.model_data import ModelDataExporter


class TestModelDataExporter:
    def test_init(self):
        exp = ModelDataExporter()
        # check the defaults
        assert exp.overwrite == False
        assert exp._filename == 'simulation_data.h5'
        assert exp._compression == 6

    @pytest.mark.xfail(reason='not implemented')
    def test_setup(self):
        exp = ModelDataExporter()
        raise NotImplementedError()
        # exp.setup(runner, state)

    @pytest.mark.xfail(reason='Not implemented')
    def test_prepare(self):
        """
        The ModelDataExporter checks if the outpath exists. It opens/creates a hdf file at the
        outpath and adds metadata to it. If file did not exist, then the state is saved through
        save_snapshot.

        Should test that:
            * file gets created
            * file has metadata
            * file non-existent: state is saved
        """

        # TODO: How to mock the state dict for `save_snapshot`?

        exp = ModelDataExporter()
        raise NotImplementedError


    @pytest.mark.xfail(reason='Not implemented')
    def test_process(self):
        # expoter.process(num, state)
        raise NotImplementedError
