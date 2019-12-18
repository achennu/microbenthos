import mock
import pytest
from fipy import PhysicalField, Variable

from microbenthos import Simulation, MicroBenthosModel
from microbenthos.model.model import ModelClock


class TestSimulation:
    def fail(self):
        pytest.xfail(reason='Not implemented')

    def test_init(self):
        sim = Simulation()
        assert sim
        assert not sim.started

    def test_started(self):
        sim = Simulation()
        with pytest.raises(AttributeError):
            sim.started = 3

    def test_fipy_solver(self):
        sim = Simulation()
        with pytest.raises(ValueError):
            sim.fipy_solver = 'abcd'

        for s in sim.FIPY_SOLVERS:
            sim.fipy_solver = s
            assert sim.fipy_solver == s

        sim._started = True
        with pytest.raises(RuntimeError):
            sim.fipy_solver = sim.FIPY_SOLVERS[1]

    def test_simtime_total(self):
        sim = Simulation()

        with pytest.raises(ValueError):
            sim.simtime_total = 0
        with pytest.raises(ValueError):
            sim.simtime_total = -3

        V = 3
        sim.simtime_total = V
        assert sim.simtime_total == PhysicalField(V, 'h')

        with pytest.raises(ValueError):
            sim.simtime_total = sim.simtime_step / 2.0

    def test_simtime_step(self):
        sim = Simulation()
        sTot = sim.simtime_total
        sMin, sMax = sim.simtime_lims
        V = 10

        sim.simtime_step = sMax * 2
        assert sim.simtime_step == sMax

        # minimum limit no longer enforced since v0.12
        # sim.simtime_step = sMin / 1.5
        # assert sim.simtime_step == sMin

        sim.simtime_step = V
        assert sim.simtime_step == PhysicalField(V, 's')

    def test_simtime_days(self):
        sim = Simulation(simtime_days=3)
        sTot = sim.simtime_total

        model = mock.MagicMock(MicroBenthosModel)
        clock = mock.MagicMock(ModelClock)
        model.clock = clock
        model.full_eqn = mock.Mock()
        model.get_object.return_value = I = mock.Mock()
        I.hours_total = 5
        sim.model = model

        model.get_object.assert_called_once_with('env.irradiance')
        assert sim.simtime_total == PhysicalField(5 * 3, 'h')

    def test_simtime_lims(self):
        sim = Simulation()
        # check the default values
        sim.simtime_lims = None
        sMin, sMax = sim.simtime_lims
        assert sMin == PhysicalField(0.1, 's')
        assert sMax == PhysicalField(120, 's')

        with pytest.raises(ValueError):
            sim.simtime_lims = (0.1, 0.001)

        sim.simtime_lims = (2, 3)
        sMin, sMax = sim.simtime_lims
        assert sMin == PhysicalField(2, 's')
        assert sMax == PhysicalField(3, 's')

    def test_max_sweeps(self):
        sim = Simulation()
        with pytest.raises(ValueError):
            sim.max_sweeps = 0

    def test_model(self):
        sim = Simulation()
        assert sim.model is None

        model = mock.MagicMock(MicroBenthosModel)
        clock = mock.MagicMock(ModelClock)
        model.clock = clock

        with pytest.raises(ValueError):
            sim.model = model
        # model interface is checked, so this is incomplete

        model.full_eqn = mock.Mock()
        sim.model = model
        assert sim.model is model

    def test_run_timestep(self):
        sim = Simulation()

        with pytest.raises(RuntimeError):
            sim.run_timestep()
            # sim.started is still False

        sim._started = True
        with pytest.raises(RuntimeError):
            sim.run_timestep()
            # no model available

        model = mock.MagicMock(MicroBenthosModel)
        clock = mock.MagicMock(ModelClock)
        model.clock = clock
        model.full_eqn = feqn = mock.Mock()
        feqn.sweep.return_value = RES = sim.max_residual

        sim.model = model

        res, nsweeps = sim.run_timestep()
        assert res == RES
        assert nsweeps == 1
        feqn.sweep.assert_called_once()

        # now test numerical failure
        feqn.sweep.side_effect = RuntimeError
        feqn._vars = mock.MagicMock()
        var = mock.Mock()
        feqn._vars.__iter__ = mock.Mock(return_value=iter([var]))

    def test_evolution(self):

        sim = Simulation()

        sim._started = True

        with pytest.raises(RuntimeError):
            for ret in sim.evolution():
                pass

        sim._started = False

        model = mock.MagicMock(MicroBenthosModel)
        clock = mock.MagicMock(ModelClock)
        clock.return_value = PhysicalField(0, 'h')
        model.clock = clock
        model.full_eqn = feqn = mock.Mock()
        feqn.sweep.return_value = RES = sim.max_residual/2

        sim.model = model

        evolution = sim.evolution()
        step, state = next(evolution)

        model.update_vars.call_count == 2
        # once before while loop starts and once for the first yield
        clock.copy.assert_called_once()

        assert step == 1
        assert isinstance(state, dict)

        step, state = next(evolution)
        clock.increment_time.assert_called_once()

    def test_get_state(self):
        sim = Simulation()

        model = mock.MagicMock(MicroBenthosModel)
        clock = mock.MagicMock(ModelClock)
        clock.return_value = PhysicalField(0, 'h')
        model.clock = clock
        model.full_eqn = feqn = mock.Mock()
        sim.model = model

        state = sim.get_state()
        assert set(state) == {'time', 'metrics'}

        statesend = dict(a=1, b=2, c=3)
        state = sim.get_state(state=statesend)

        sent = set(statesend)
        sent.update(('metrics',))
        assert set(state) == sent

        V = 30
        for m in ('calc_time', 'residual', 'num_sweeps'):
            state = sim.get_state(**{m: V})
            assert state['metrics'][m]['data'][0] == V

    def test_snapshot_due(self):
        sim = Simulation()

        model = mock.MagicMock(MicroBenthosModel)
        clock = mock.MagicMock(ModelClock)
        clock.return_value = C = PhysicalField(3, 'h')
        model.clock = clock
        model.full_eqn = feqn = mock.Mock()
        sim.model = model

        sim._prev_snapshot = Variable(C - sim.snapshot_interval / 2.0)
        assert not sim.snapshot_due()

        sim._prev_snapshot = Variable(C - sim.snapshot_interval * 1.01)
        assert sim.snapshot_due()


        # def test_update_simtime_step(self):
        #     pass
