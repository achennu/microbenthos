import io
import tempfile

import mock
import pytest

from microbenthos.model import Simulation
from microbenthos.runners import SimulationRunner
from microbenthos.utils import yaml


@pytest.fixture()
def model():
    with mock.patch('microbenthos.model.MicroBenthosModel', autospec=True) as Model:
        with mock.patch('microbenthos.model.ModelClock', autospec=True) as Clock:
            model = Model()
            model.clock = Clock(model)
            yield model


@pytest.fixture()
def model_with_eqn(model):
    with mock.patch('fipy.terms.binaryTerm._BinaryTerm', spec=True) as BinaryTerm:
        model.full_eqn = BinaryTerm()
        yield model


SIMULATION_DEF = """
simtime_total: !unit 1 h
simtime_step: !unit 120 s
residual_lim: 1e-6
max_sweeps: 15
fipy_solver: scipy
"""


class TestSimulation:
    def test_init(self):
        sim = Simulation()
        assert sim
        assert sim.started is False

    @pytest.mark.parametrize('obj', [
        SIMULATION_DEF,
        io.StringIO(unicode(SIMULATION_DEF)),
        yaml.load(io.StringIO(unicode(SIMULATION_DEF)))
        ],
         ids=('string', 'stream', 'dict'))
    def test_create_from(self, obj):
        s = Simulation.create_from(obj)
        assert s
        assert s.started == False

    @pytest.mark.parametrize(
        'solver', (None,) + Simulation.FIPY_SOLVERS
        )
    def test_fipy_solver(self, solver):

        if solver in Simulation.FIPY_SOLVERS:
            sim = Simulation(fipy_solver=solver)
            assert sim.fipy_solver == solver

            sim._started = True
            with pytest.raises(RuntimeError):
                sim.fipy_solver = solver

        else:
            with pytest.raises(ValueError):
                sim = Simulation(fipy_solver=solver)

    @pytest.mark.parametrize(
        'total,step,error',
        # hours, seconds, exception
        [
            (None, None, ValueError),
            (1, None, ValueError),
            (-1, None, ValueError),
            (1, 3, None),
            (1, 3600 - 1, None),
            (1, 3600, ValueError),
            ]
        )
    def test_simtime(self, total, step, error):

        if error:
            with pytest.raises(error):
                sim = Simulation(simtime_total=total, simtime_step=step)

        else:
            sim = Simulation(simtime_total=total, simtime_step=step)
            assert sim

    @pytest.mark.parametrize('res, error', [
        (None, ValueError),
        (2e-6, ValueError),
        (1e-6, None),
        (1e-12, None),
        ]
                             )
    def test_residual_lim(self, res, error):
        if error:
            with pytest.raises(error):
                sim = Simulation(residual_lim=res)

        else:
            sim = Simulation(residual_lim=res)
            assert sim

    @pytest.mark.parametrize('sweeps, error', [
        (None, ValueError),
        (0, ValueError),
        (1, ValueError),
        (2, None),
        (8.5, None),
        ]
                             )
    def test_max_sweeps(self, sweeps, error):
        if error:
            with pytest.raises(error):
                sim = Simulation(max_sweeps=sweeps)

        else:
            sim = Simulation(max_sweeps=sweeps)
            assert sim

    def test_set_model(self, model):

        sim = Simulation()
        with pytest.raises(ValueError):
            sim.model = None
        with pytest.raises(ValueError):
            sim.model = object()

        sim = Simulation()

        with pytest.raises(ValueError):
            sim.model = model
            # model.full_eqn is None, so create_full_equation is called once
            model.create_full_equation.assert_called_once_with(model)

        assert sim.model is None
        model.full_eqn = object()
        with pytest.raises(ValueError):
            sim.model = model
            # when full_eqn is not a binary term

        with mock.patch('fipy.terms.binaryTerm._BinaryTerm', spec=True) as BinaryTerm:
            assert sim.model is None
            model.full_eqn = BinaryTerm()
            sim.model = model
            assert sim.model is model

            with pytest.raises(RuntimeError):
                # because model already set
                sim.model = model

    def test_start(self, model_with_eqn):
        sim = Simulation()
        sim.model = model_with_eqn

        sim.start()
        assert sim.started

        with pytest.raises(RuntimeError):
            sim.start()

    def test_run_timestep(self, model_with_eqn):

        model = model_with_eqn
        sim = Simulation()
        sim.model = model
        sim.start()
        assert sim.started

        RES = sim.residual_lim / 10
        model.full_eqn.sweep.return_value = RES

        dt = sim.simtime_step

        res = sim.run_timestep()
        model.full_eqn.sweep.assert_called_once()
        model.clock.increment_time.assert_not_called()
        model.update_vars.assert_called_once()
        model.update_equations.assert_called_once_with(dt)

        assert res == RES

    def test_simulation_evolution(self):
        pytest.xfail('Not implemented!')
        odir = tempfile.mkdtemp()
        runner = SimulationRunner(output_dir=odir)

        simulation = mock.Mock(Simulation)
        runner.simulation = simulation
        runner.model = simulation.model

        simulation.model.snapshot.return_value = {}
        simulation.simtime_step.return_value = dt = object()

        runner.simulation = SIMULATION_DEF
        runner.model = model
        runner.prepare_simulation()

        total = runner.simulation.total_steps

        # now run evolution
        with mock.patch.object(runner.simulation, 'run_timestep') as obj:
            for step in runner.simulation.evolution():
                num, snap = step
                assert isinstance(num, int)
                assert num <= total
                assert isinstance(snap, dict)

            assert obj.call_count == total
            assert simulation.model.clock.increment_time.call_count == total
            assert simulation.model.clock.increment_timme.called_with(dt)
