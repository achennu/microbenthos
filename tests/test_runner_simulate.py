import logging
import os
import tempfile

import mock
import pytest
from microbenthos import yaml
from microbenthos.runners.simulate import SimulationRunner

from .test_model import MODEL_DEF
from .test_simulation import SIMULATION_DEF


@pytest.fixture()
def model():
    from microbenthos.model.model import MicroBenthosModel, ModelClock
    from fipy.terms.binaryTerm import _BinaryTerm

    model = mock.Mock(spec=MicroBenthosModel)
    # model = ModelMock()
    model.clock = mock.Mock(spec=ModelClock)
    model.full_eqn = mock.Mock(spec=_BinaryTerm)
    return model

@pytest.fixture()
def simulation():
    from microbenthos.model.simulation import Simulation
    sim = mock.Mock(spec=Simulation)
    return sim


class TestRunner:

    def test_init(self):

        runner = SimulationRunner()
        assert runner

    @pytest.mark.xfail(reason='Definition dict not updated to new schema.yml')
    def test_set_model(self):
        runner = SimulationRunner(model=MODEL_DEF)
        assert runner.model is not None

    @pytest.mark.xfail(reason='Definition dict not updated to new schema.yml')
    def test_set_simulation(self):
        runner = SimulationRunner(simulation=SIMULATION_DEF)
        assert runner.simulation is not None

    def test_create_output_dir(self):

        runner = SimulationRunner()

        with pytest.raises(ValueError):
            runner._create_output_dir()

        # dir exists
        DIR = tempfile.mkdtemp()
        runner.output_dir = DIR
        assert os.path.isdir(runner.output_dir)

        # dir doesn't exist
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

        with open(logpath) as fp:
            ll = fp.readlines()

        print(ll)

    def test_teardown_logfile(self):
        runner = SimulationRunner(output_dir=tempfile.mkdtemp())

        runner.teardown_logfile()
        # check that this doesn't raise an error even if not setup

        runner.setup_logfile()
        logger = logging.getLogger('microbenthos')
        assert runner._log_fh in logger.handlers

        runner.teardown_logfile()
        assert runner._log_fh not in logger.handlers

    def test_save_definitions(self, model, simulation):
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir)
        runner.model = model
        runner.simulation = simulation

        path = os.path.join(odir, 'model.yml')
        runner.save_definitions()
        assert os.path.isfile(path)
        with open(path) as fp:
            definition = yaml.load(fp)
        assert 'model' in definition
        assert 'simulation' in definition

    def test_save_runinfo(self):
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir)
        path = os.path.join(odir, 'runner.yml')

        runner.save_run_info()
        assert os.path.isfile(path)

        with open(path) as fp:
            definition = yaml.load(fp)
        assert 'libraries' in definition
        assert 'exporters' in definition
        assert 'runner' in definition
        assert 'cls' in definition['runner']

    @pytest.mark.xfail(reason='Definition dict not updated to new schema.yml')
    def test_prepare_sim(self, model):
        runner = SimulationRunner()
        runner.simulation = SIMULATION_DEF

        runner.prepare_simulation()
        assert runner.simulation.model is None

        assert model
        runner.model = model

        runner.prepare_simulation()
        print(model)
        print(bool(model))
        print(runner.simulation)
        print(runner.model)
        print(runner.simulation.model)

        assert runner.simulation.model is model


    def test_exporters_context(self):
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir)

        with mock.patch('microbenthos.exporters.exporter.BaseExporter', autospec=True) as Exporter:
            Exporter.return_value.started = False
            runner.exporters['a'] = Exporter()

            if not runner.exporters:
                pytest.xfail('No exporters defined!')

            exps = runner.exporters.values()
            # assert all(not exp.started for exp in exps)

            with runner.exporters_activated():
                for exp in exps:
                    exp.setup.assert_called_once_with(runner)
                    exp.started = True

                # assert all(exp.started for exp in exps)

            for exp in exps:
                exp.close.assert_called_once_with()

    def test_run(self):

        mocked = mock.MagicMock(spec=SimulationRunner())

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
        pytest.xfail('Not implemented')
        SimulationRunner.add_exporter()
