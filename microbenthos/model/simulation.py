"""
Module to handle the simulation of microbenthos models
"""

import importlib
import logging
import math
import time

from fipy import PhysicalField, Variable

from .model import MicroBenthosModel
from ..utils import CreateMixin, snapshot_var


class Simulation(CreateMixin):
    """
    Class that encapsulates the functionality for running a simulation on a MicroBenthos model
    instance.
    """
    schema_key = 'simulation'

    FIPY_SOLVERS = ('scipy', 'trilinos', 'pysparse')

    def __init__(self,
                 simtime_total = 6,
                 simtime_step = 30,
                 simtime_days = None,
                 simtime_lims = None,
                 simtime_adaptive = True,
                 snapshot_interval = 60,
                 residual_target = 1e-12,
                 residual_break = 1e-3,
                 max_sweeps = 10,
                 fipy_solver = 'scipy'
                 ):
        """
        Initialize the Simulation with parameters

        Args:
            simtime_total (float): The number of hours for the simulation to run

            simtime_step (float) Number of seconds in each simulation step

            simtime_days (float): The number of days (in terms of the
            model's irradiance cycle) the simulation should run for. Note that specifying this
            will override the given `simtime_total` when the :attr:`.model` is supplied.

            simtime_lims (float, float): The limits for the :attr:`simtime_step`. This is useful
            when an adaptive time step is used, but hard limits are necessary.

            simtime_adaptive (bool): If the :attr:`simtime_step` should adapt to the residual of
            the simulation evolution (default: False).

            snapshot_interval (int, float, :class:`PhysicalField`): the duration in seconds between
            taking snapshots of the model for exporters (default: 60 seconds)

            residual_target (float): The max residual limit below which the timestep is considered
            to be numerically accurate

            residual_break (float): Residual at a time step above this value will cause the
            simulation to abort

            max_sweeps (int): Number of sweeps to use within the timestep

            fipy_solver (str): Name of the fipy solver to use
        """
        super(Simulation, self).__init__()
        # the __init__ call is deliberately empty. will implement cooeperative inheritance only
        # when necessary
        self.logger = logging.getLogger(__name__)
        self._started = False
        self._solver = None

        self._fipy_solver = None
        self.fipy_solver = fipy_solver

        self._simtime_lims = None
        self._simtime_total = None
        self._simtime_step = None
        self.simtime_days = None

        if simtime_days:
            simtime_days = float(simtime_days)
            if simtime_days <= 0:
                raise ValueError('simtime_days should be >0, not {:.2f}'.format(simtime_days))
            self.simtime_days = simtime_days

        self.simtime_adaptive = bool(simtime_adaptive)
        self.simtime_total = simtime_total
        self.simtime_lims = simtime_lims
        self.simtime_step = simtime_step

        self.snapshot_interval = PhysicalField(snapshot_interval, 's')

        self._residual_target = None
        self.residual_target = residual_target
        self.residual_break = float(residual_break)
        assert self.residual_break > 0

        self._max_sweeps = None
        self.max_sweeps = max_sweeps

        self._model = None

    @property
    def started(self):
        return self._started

    @property
    def fipy_solver(self):
        return self._fipy_solver

    @fipy_solver.setter
    def fipy_solver(self, val):
        if val not in self.FIPY_SOLVERS:
            raise ValueError('Solver {!r} not in {}'.format(val, self.FIPY_SOLVERS))

        if self.started:
            raise RuntimeError('Fipy solver cannot be changed after started')

        self._fipy_solver = val

    @property
    def simtime_total(self):
        return self._simtime_total

    @simtime_total.setter
    def simtime_total(self, val):
        try:
            val = PhysicalField(val, 'h')
        except TypeError:
            raise ValueError('simtime_total {!r} not compatible with time units'.format(val))

        if val <= 0:
            raise ValueError('simtime_total should be > 0')

        if self.simtime_step is not None:
            if val <= self.simtime_step:
                raise ValueError(
                    'simtime_total {} should be > step {}'.format(val, self.simtime_step))

        self._simtime_total = val

    @property
    def simtime_step(self):
        return self._simtime_step

    @simtime_step.setter
    def simtime_step(self, val):
        try:
            val = PhysicalField(val, 's')
        except TypeError:
            raise ValueError('simtime_step {!r} not compatible with time units'.format(val))

        if val <= 0:
            raise ValueError('simtime_step should be > 0')

        dtMin, dtMax = self.simtime_lims
        val = min(max(val, dtMin), dtMax)
        assert hasattr(val, 'unit')

        if self.simtime_total is not None:
            if self.simtime_total <= val:
                raise ValueError(
                    'simtime_total {} should be > step {}'.format(self.simtime_total, val))

        self._simtime_step = val

    @property
    def total_steps(self):
        try:
            return int(math.ceil(self.simtime_total / self.simtime_step))
        except:
            self.logger.error(
                "Could not determine total_steps from simtime_total = {} "
                "and simtime_step = {}".format(
                    self.simtime_total, self.simtime_step))

    @property
    def simtime_lims(self):
        return self._simtime_lims

    @simtime_lims.setter
    def simtime_lims(self, vals):
        if vals is None:
            lmin = PhysicalField(1, 's')
            # lmax = (self.simtime_total / 25.0).inUnitsOf('s').floor()
            lmax = PhysicalField(300, 's')
        else:
            lmin, lmax = [PhysicalField(_, 's') for _ in vals]
        assert 0 < lmin < lmax, 'simtime_lims ({}, {}) are not positive and in order'.format(
            lmin, lmax)
        self._simtime_lims = (lmin, lmax)
        self.logger.debug('simtime_lims set: {}'.format(self._simtime_lims))

    @property
    def residual_target(self):
        return self._residual_target

    @residual_target.setter
    def residual_target(self, val):
        try:
            val = float(val)
            assert val <= 1e-6
            self._residual_target = val
        except:
            raise ValueError('residual_target {} should be <= 1e-6'.format(val))

    @property
    def max_sweeps(self):
        return self._max_sweeps

    @max_sweeps.setter
    def max_sweeps(self, val):
        try:
            val = int(val)
            assert val > 1
            self._max_sweeps = val
        except:
            raise ValueError('max_sweeps {} should be > 1'.format(val))

    @property
    def model(self):
        """
        The model to run the simulation on. This is typically an instance of
        :class:`~microbenthos.MicroBenthosModel` or its subclasses. The interface it must
        provide is:

        * a method :meth:`create_full_equation()`
        * an attribute :attr:`full_eqn` created by above method, which is a
        :class:`~fipy.terms.binaryTerm._BinaryTerm` that has a :meth:`sweep()` method.
        * method :meth:`update_vars()` which is called before each timestep
        * method :meth:`model.clock.increment_time(dt)` which is called after each timestep
        """
        return self._model

    @model.setter
    def model(self, m):
        """
        The model to operate the simulation on

        Args:
            m (MicroBenthosModel): The model instance

        """

        if self.model:
            raise RuntimeError('Model already set')

        full_eqn = getattr(m, 'full_eqn', None)
        if full_eqn is None:
            if hasattr(m, 'create_full_equation'):
                m.create_full_equation()
        full_eqn = getattr(m, 'full_eqn', None)
        if full_eqn is None:
            raise ValueError(
                'Model {!r} (type={}) does not have a valid equation'.format(m, type(m)))

        # if not isinstance(full_eqn, _BinaryTerm):
        #     raise TypeError(
        #         'Model {!r} equation is not a fipy BinaryTerm: {}'.format(m, type(full_eqn)))

        def recursive_hasattr(obj, path, is_callable = False):
            parts = path.split('.')
            S = obj
            FOUND = False
            for p in parts:
                if hasattr(S, p):
                    S = getattr(S, p)
                    FOUND = True
                else:
                    FOUND = False
                    break

            if not FOUND:
                return False
            else:
                if is_callable:
                    return callable(S)
                else:
                    return True

        expected_attrs = ['clock', 'full_eqn']
        expected_callables = ['full_eqn.sweep', 'update_vars', 'clock.increment_time']
        failed_attrs = filter(lambda x: not recursive_hasattr(m, x), expected_attrs)
        failed_callables = filter(lambda x: not recursive_hasattr(m, x, is_callable=True),
                                  expected_callables)

        if failed_attrs:
            self.logger.error('Model is missing required attributes: {}'.format(failed_attrs))
        if failed_callables:
            self.logger.error('Model is missing required callables: {}'.format(failed_callables))

        if failed_callables or failed_attrs:
            raise ValueError(
                'Model interface is missing: {}'.format(set(failed_attrs + failed_callables)))

        self._model = m

        # if simtime_days is given, override the simtime_total with it
        if self.simtime_days is not None:
            I = self.model.get_object('env.irradiance')
            simtime_total = self.simtime_days * I.hours_total
            self.logger.warning('Setting simtime_total={} for {} days of simtime'.format(
                simtime_total, self.simtime_days
                ))
            self.simtime_total = simtime_total

    def start(self):
        """
        Start the simulation

        Performs the setup for running the simulation with :meth:`.run_timestep`
        """
        if self.started:
            raise RuntimeError('Simulation already started!')

        self.logger.info('Starting simulation')
        self.logger.debug(
            'simtime_total={o.simtime_total} simtime_step={o.simtime_step}, residual_target='
            '{o.residual_target} max_sweeps={o.max_sweeps}'.format(
                o=self))

        solver_module = importlib.import_module('fipy.solvers.{}'.format(self.fipy_solver))
        Solver = getattr(solver_module, 'DefaultSolver')
        self._solver = Solver()
        self.logger.debug('Created fipy {} solver: {}'.format(self.fipy_solver, self._solver))

        self._started = True

    def run_timestep(self):
        """
        Evolve the model through a single timestep
        """
        if not self.started:
            raise RuntimeError('Simulation timestep cannot be run since started=False')

        dt = self.simtime_step
        self.logger.info('Running timestep {} + {}'.format(self.model.clock, dt))

        num_sweeps = 1
        res = 1

        EQN = self.model.full_eqn

        while (res > self.residual_target) and (num_sweeps <= self.max_sweeps):
            res = EQN.sweep(
                solver=self._solver,
                dt=float(dt.numericValue)
                )
            num_sweeps += 1
            self.logger.debug('Sweeps: {}  residual: {:.2g}'.format(num_sweeps, float(res)))

        if res > self.residual_target:
            self.logger.info('Timestep residual {:.2g} > limit {:.2g} sweeps={}'.format(
                res, self.residual_target, num_sweeps))

            if res > self.residual_break:
                self.logger.warning('Residual {:.2g} too high (>{:.2g})'.format(
                    res,
                    self.residual_break
                    ))
                # raise RuntimeError('Residual {:.2g} too high (>{:.2g}) to continue'.format(
                #     res,
                #     self.residual_break
                #     ))

        self.model.update_vars()
        self.model.update_equations(dt)

        return res, num_sweeps

    def evolution(self):
        """
        Evolves the model clock through the time steps for the simulation.

        This yields the initial model state, followed by a snapshot for every time step. Along
        with the model state, some metrics of the simulation run are injected into the state
        dictionary.

        Yields:
            `(step, state)` tuple of step number and model state

        """

        # TODO: uncouple state yield time from time step, esp for small time steps

        self.logger.info('Simulation evolution starting')
        self.logger.debug('Solving: {}'.format(self.model.full_eqn))
        self.start()

        self.model.update_vars()

        step = 0

        # yield the initial condition first
        state = self.model.snapshot()
        residual = 0
        calc_time = 0
        state['metrics'] = dict(
            calc_times=dict(data=(calc_time, dict(unit='ms'))),
            residuals=dict(data=(residual, None)),
            sweeps=dict(data=(0, None)),
            )
        self._prev_snapshot = Variable(self.model.clock, name='prev_snapshot')
        yield (step, state)

        while self.model.clock() < self.simtime_total:
            step += 1
            self.logger.debug('Running step #{} {}'.format(step, self.model.clock))

            tic = time.time()
            residual, num_sweeps = self.run_timestep()
            toc = time.time()

            if self.simtime_adaptive:
                self.update_simtime_step(residual, num_sweeps)

            calc_time = 1000 * (toc - tic)
            self.logger.debug('Timestep done in {:.2f} msec'.format(calc_time))

            metrics = dict(
                calc_times=dict(data=(calc_time, dict(unit='ms'))),
                residuals=dict(data=(residual, None)),
                sweeps=dict(data=(num_sweeps, None))
                )

            if self.export_due():

                self.logger.debug('Snapshot in step #{}'.format(step))

                state = self.model.snapshot()
                state['metrics'] = metrics

                yield (step, state)

                # now set the prev_snapshot so that export_due() will remain true for processing
                self._prev_snapshot.setValue(self.model.clock())
                self.logger.debug('Prev snapshot set: {}'.format(self._prev_snapshot))

            else:
                # create a minimal state
                # this is the model clock and current residual
                state = dict(
                    time=dict(data=snapshot_var(self.model.clock)),
                    metrics=metrics
                    )

                yield (step, state)

            self.model.clock.increment_time(self.simtime_step)

        # now yield final state
        yield (step, self.model.snapshot())

        self.logger.info('Simulation evolution completed')

    def export_due(self):
        return self.model.clock() - self._prev_snapshot() >= self.snapshot_interval

    def update_simtime_step(self, residual, num_sweeps):
        """
        Update the simtime_step to be adaptive to the current residual

        A multiplicative factor is determined based on the number of sweeps and residual
        undershoot when the residual is below :attr:`residual_target`. If not, the multiplicative
        factor penalizes the residual overshoot by setting the factor < 1.

        Args:
            residual (float): the residual from the last equation step
            num_sweeps (int): the number of sweeps from the last equation step

        """
        self.logger.debug('Updating step {} after {}/{} sweeps and {:.3g}/{:.3g} residual'.format(
            self.simtime_step, num_sweeps, self.max_sweeps, residual, self.residual_target
            ))

        residual_factor = math.log10(self.residual_target / (residual + 1e-30)) * 0.05

        if residual <= self.residual_target:

            # if self.simtime_step < self.simtime_lims[1]:
            mult = 1.0 + math.log10(0.5 * (self.max_sweeps) / num_sweeps) + residual_factor
            self.logger.debug(
                'Residual ok. Multiplier: {:.4f} '.format(mult))

        else:
            mult = 10 ** (residual_factor * 5)
            self.logger.debug('Penalizing by {:.3g} due to overshoot'.format(mult))

        self.simtime_step *= mult

        self.simtime_step = min(self.simtime_step, self.simtime_total - self.model.clock())
        self.logger.debug('Updated simtime_step: {}'.format(self.simtime_step))
