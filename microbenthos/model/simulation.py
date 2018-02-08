"""
Module to handle the simulation of microbenthos models
"""

import importlib
import logging
import math
import time

from fipy import PhysicalField

from ..utils import CreateMixin


class Simulation(CreateMixin):
    """
    Class that encapsulates the functionality for running a simulation on a MicroBenthos model
    instance.
    """
    schema_key = 'simulation'

    FIPY_SOLVERS = ('scipy', 'trilinos', 'pysparse')

    def __init__(self,
                 simtime_total = 6,
                 simtime_step = 120,
                 simtime_days = 1,
                 residual_lim = 1e-8,
                 max_sweeps = 25,
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
            residual_lim (float): The max residual limit below which the timestep is considered
            to be numerically accurate
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

        self._simtime_total = None
        self._simtime_step = None
        self.simtime_days = 0

        if simtime_days:
            simtime_days = float(simtime_days)
            if simtime_days <= 0:
                raise ValueError('simtime_days should be >0, not {:.2f}'.format(simtime_days))
            self.simtime_days = simtime_days

        self.simtime_total = simtime_total
        self.simtime_step = simtime_step

        self._residual_lim = None
        self.residual_lim = residual_lim

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
    def residual_lim(self):
        return self._residual_lim

    @residual_lim.setter
    def residual_lim(self, val):
        try:
            val = float(val)
            assert val <= 1e-6
            self._residual_lim = val
        except:
            raise ValueError('residual_lim {} should be <= 1e-6'.format(val))

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
            'simtime_total={o.simtime_total} simtime_step={o.simtime_step}, residual_lim='
            '{o.residual_lim} max_sweeps={o.max_sweeps}'.format(
                o=self))

        solver_module = importlib.import_module('fipy.solvers.{}'.format(self.fipy_solver))
        Solver = getattr(solver_module, 'DefaultSolver')
        self._solver = Solver()
        self.logger.debug('Created fipy {} solver: {}'.format(self.fipy_solver, self._solver))

        self._started = True
        self.calc_times = []
        self.residuals = []

    def run_timestep(self):
        """
        Evolve the model through a single timestep
        Args:
            dt:

        Returns:
        """
        if not self.started:
            raise RuntimeError('Simulation timestep cannot be run since started=False')

        dt = self.simtime_step
        self.logger.info('Running timestep {} + {}'.format(self.model.clock, dt))

        num_sweeps = 0
        res = 1

        EQN = self.model.full_eqn

        self.model.update_vars()

        while (res > self.residual_lim) and (num_sweeps < self.max_sweeps):
            res = EQN.sweep(
                solver=self._solver,
                dt=float(dt.numericValue)
                )
            num_sweeps += 1
            self.logger.debug('Sweeps: {}  residual: {:.2g}'.format(num_sweeps, float(res)))

        if res > self.residual_lim:
            self.logger.warning('Timestep residual {:.2g} > limit {:.2g}'.format(
                res, self.residual_lim))
            if res > 0.1:
                raise RuntimeError('Residual {:.2g} too high to continue'.format(res))

        self.model.clock.increment_time(dt)

        return res

    def evolution(self):
        self.logger.info('Simulation evolution starting')
        self.start()

        # yield the initial condition first
        self.model.update_vars()
        yield (0, self.model.snapshot())

        for step in range(1, self.total_steps + 1):
            self.logger.debug('Running step #{}'.format(step))

            tic = time.time()
            residual = self.run_timestep()
            toc = time.time()

            self.residuals.append(residual)
            calc_time = 1000 * (toc - tic)
            self.calc_times.append(calc_time)
            self.logger.debug('Timestep done in {:.2f} msec'.format(calc_time))

            state = self.model.snapshot()
            state['metrics'] = dict(
                calc_times=dict(data=(calc_time, dict(unit='ms'))),
                residuals=dict(data=(residual, None))
                )

            yield (step, state)

        self.logger.info('Simulation evolution completed')
