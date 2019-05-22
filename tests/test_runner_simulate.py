import logging
import os
import tempfile

import mock
import pytest
from fipy import PhysicalField

from microbenthos import yaml, MicroBenthosModel, Simulation
from microbenthos.model.model import ModelClock
from microbenthos.runners.simulate import SimulationRunner


@pytest.fixture()
def model():
    model = mock.MagicMock(MicroBenthosModel)
    clock = mock.MagicMock(ModelClock)
    clock.return_value = C = PhysicalField(3, 'h')
    model.clock = clock
    model.full_eqn = feqn = mock.Mock()
    return model


@pytest.fixture()
def sim():
    sim = Simulation()
    return sim


class TestSimulationRunner:
    def test_init(self, sim, model):
        runner = SimulationRunner()
        assert runner

        runner = SimulationRunner(simulation=sim)
        assert runner.simulation is sim

        runner = SimulationRunner(model=model)
        assert runner.model is model

        runner = SimulationRunner(model=model, simulation=sim)
        assert runner.simulation.model is model

        runner = SimulationRunner()
        runner.model = model
        runner.simulation = sim
        assert runner.simulation.model is model

    def test_create_output_dir(self):
        runner = SimulationRunner()

        # dir exists
        DIR = tempfile.mkdtemp()
        runner.output_dir = DIR
        assert os.path.isdir(runner.output_dir)

        # dir doesn't exist, is created
        runner.output_dir = DIR + 'abc'
        runner._create_output_dir()
        assert os.path.isdir(runner.output_dir)

        # what happens when the path is already a file
        fp, FILE = tempfile.mkstemp()
        runner.output_dir = FILE
        with pytest.raises(OSError):
            runner._create_output_dir()

    def test_setup_logfile(self):
        runner = SimulationRunner(output_dir=tempfile.mkdtemp())
        logpath = os.path.join(runner.output_dir, 'simulation.log')

        assert not os.path.isfile(logpath)
        runner.setup_logfile()
        assert os.path.isfile(logpath)
        assert runner._log_fh
        logger = logging.getLogger('microbenthos')
        assert runner._log_fh in logger.handlers

    def test_teardown_logfile(self):
        runner = SimulationRunner(output_dir=tempfile.mkdtemp())

        runner.teardown_logfile()
        # check that this doesn't raise an error even if not setup

        runner.setup_logfile()
        logger = logging.getLogger('microbenthos')
        assert runner._log_fh in logger.handlers

        runner.teardown_logfile()
        assert runner._log_fh not in logger.handlers

    def test_save_definitions(self, model, sim):
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir)
        runner.model = model
        runner.simulation = sim

        path = os.path.join(odir, 'definition.yml')
        runner.save_definitions()
        assert os.path.isfile(path)
        with open(path) as fp:
            definition = yaml.unsafe_load(fp)
        assert 'model' in definition
        assert 'simulation' in definition

    def test_save_runinfo(self):
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir)
        path = os.path.join(odir, 'runner.yml')

        runner.save_run_info()
        assert os.path.isfile(path)

        with open(path) as fp:
            definition = yaml.unsafe_load(fp)
        assert 'libraries' in definition
        assert 'exporters' in definition
        assert 'runner' in definition
        assert 'cls' in definition['runner']

    def test_prepare_sim(self, model, sim):
        runner = SimulationRunner()
        runner.simulation = sim

        runner.prepare_simulation()
        assert runner.simulation.model is None

        assert model
        runner.model = model

        runner.prepare_simulation()
        assert runner.simulation.model is model

    def test_exporters_context(self, sim, model):
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir,
                                  simulation=sim,
                                  model=model)
        assert not runner.exporters

        from microbenthos import BaseExporter

        MExporter = mock.MagicMock(BaseExporter)
        exp = MExporter()
        state = sim.get_state(sim.model.snapshot())

        runner.exporters['a'] = exp

        with runner.exporters_activated():
            exp.setup.assert_called_once_with(runner, state)
            exp.started = True

        exp.close.assert_called_once()

    def test_run(self, model, sim):
        runner = SimulationRunner(simulation=sim, model=model)
        mocked = mock.MagicMock(runner)

        mocked.confirm = False

        print(sim.simtime_lims)

        SimulationRunner.run(mocked)

        mocked.check_simulation.assert_called_once()

        mocked._create_output_dir.assert_called_once()

        mocked.setup_logfile.assert_called_once()

        mocked.save_definitions.assert_called_once()

        mocked.save_run_info.assert_called_once()

        mocked.prepare_simulation.assert_called_once()

        mocked.exporters_activated.assert_called_once()

        mocked.simulation.evolution.assert_called_once()

        mocked.teardown_logfile.assert_called_once()

    def test_add_exporter(self):
        runner = SimulationRunner()
        with pytest.raises(ValueError):
            runner.add_exporter('abc', 'myexporter')

        print(runner._exporter_classes)
        for etype in runner._exporter_classes:
            print('Adding {}'.format(etype))
            runner.add_exporter(etype)
            assert etype in runner.exporters

        runner.add_exporter(etype, 'me')
        assert 'me' in runner.exporters
        with pytest.raises(ValueError):
            runner.add_exporter(etype, 'me')
            # name already exists
