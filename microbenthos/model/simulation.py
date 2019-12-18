"""
Module to handle the simulation of microbenthos models
"""
from __future__ import division

import importlib
import logging
import time
from collections import deque

from fipy import PhysicalField, Variable

from .model import MicroBenthosModel
from ..utils import CreateMixin, snapshot_var


class Simulation(CreateMixin):
    """
    This class enables the process of repeatedly solving the model's
    equations for a (small) time step to a certain numerical accuracy,
    and then incrementing the model clock. During the evolution of the
    simulation, the state of the model as well as the simulation is yielded
    repeatedly.

    Numerically approximating the solution to a set of partial differential
    equations requires that the solver system has a reasonable target accuracy
    ("residual") and enough attempts ("sweeps") to reach both a stable and
    accurate approximation for a time step. This class attempts to abstract out
    these optimizations for the user, by performing adaptive time-stepping. The
    user needs to specify a worst-case residual ( :attr:`.max_residual`),
    maximum number of sweeps per time-step ( :attr:`.max_sweeps`) and the range
    of time-step values to explore during evolution (:attr:`.simtime_lims`).
    During the evolution of the simulation, the time-step is penalized if the
    max residual is overshot or max sweeps reached. If not, the reward is a bump
    up in the time-step duration, allowing for faster evolution of the
    simulation.

    See Also:
         The scheme of simulation :meth:`.evolution`.

         The adaptive scheme to :meth:`.update_time_step`.

    """
    schema_key = 'simulation'

    FIPY_SOLVERS = ('scipy', 'pyAMG', 'trilinos', 'pysparse')

    def __init__(self,
                 simtime_total = 6,
                 simtime_days = None,
                 simtime_lims=(0.1, 120),
                 snapshot_interval = 60,
                 fipy_solver = 'scipy',
                 max_sweeps=100,
                 max_residual=1e-12,
                 ):
        """
        Args:
            simtime_total (float, PhysicalField): The number of hours for the
            simulation to run

            simtime_days (float): The number of days (in terms of the
                model's irradiance cycle) the simulation should run for. Note
                that specifying this
                will override the given :attr:`.simtime_total` when the
                :attr:`.model` is supplied.

            simtime_lims (float, PhysicalField): The minimum and maximum
            limits for the
                :attr:`simtime_step` for adaptive time-stepping. This should
                be supplied as a
                pair of values, which are assumed to be in seconds and cast
                into PhysicalField
                internally. (default: 0.01, 240)

            max_sweeps (int): Maximum number of sweeps to attempt per
            timestep (default: 50)

            max_residual (float): Maximum residual value for the solver at a
            timestep (default:
                1e-14)

            snapshot_interval (int, float, :class:`PhysicalField`): the
            duration in seconds
                of the model clock between yielding snapshots of the model
                state for exporters
                (default: 60)

            fipy_solver (str): Name of the fipy solver to use. One of
                            ``('scipy', 'pyAMG', 'trilinos','pysparse')`` (default: "scipy")

        """
        super(Simulation, self).__init__()
        # the __init__ call is deliberately empty. will implement
        # cooeperative inheritance only
        # when necessary
        self.logger = logging.getLogger(__name__)
        self._started = False
        self._solver = None

        self._fipy_solver = None
        self.fipy_solver = fipy_solver

        self._simtime_lims = None
        self._simtime_total = None
        self._simtime_step = None

        #: Numer of days to simulate in terms of the model's irradiance source
        self.simtime_days = None

        if simtime_days:
            simtime_days = float(simtime_days)
            if simtime_days <= 0:
                raise ValueError('simtime_days should be >0, not {:.2f}'.format(
                    simtime_days))
            self.simtime_days = simtime_days

        self.simtime_lims = simtime_lims

        self.simtime_total = simtime_total

        self.simtime_step = self.simtime_lims[0]

        self.snapshot_interval = PhysicalField(snapshot_interval, 's')

        self.max_residual = float(max_residual)
        if not (0 < self.max_residual < 1e-3):
            raise ValueError(
                'Max residual should be a small positive number, '
                'not {:.3g}'.format(
                    self.max_residual))

        self._residualQ = deque([], maxlen=10)

        self._max_sweeps = None
        self.max_sweeps = max_sweeps
        self._sweepsQ = deque([], maxlen=5)

        self._model = None

    @property
    def started(self):
        """
        Returns:
            bool: Flag for if the sim evolution has started

        """
        return self._started

    @property
    def fipy_solver(self):
        return self._fipy_solver

    @fipy_solver.setter
    def fipy_solver(self, val):
        if val not in self.FIPY_SOLVERS:
            raise ValueError(
                'Solver {!r} not in {}'.format(val, self.FIPY_SOLVERS))

        if self.started:
            raise RuntimeError('Fipy solver cannot be changed after started')

        self._fipy_solver = val

    @property
    def simtime_total(self):
        """
        The number of hours of the model clock the simulation should be
        evolved for.

        The supplied value must be larger than the time-steps allowed. Also, it
        may be over-ridden by supplying :attr:`.simtime_days`.

        Returns:
            PhysicalField: duration in hours

        """
        return self._simtime_total

    @simtime_total.setter
    def simtime_total(self, val):
        try:
            val = PhysicalField(val, 'h')
        except TypeError:
            raise ValueError(
                'simtime_total {!r} not compatible with time units'.format(val))

        if val <= 0:
            raise ValueError('simtime_total should be > 0')

        if self.simtime_step is not None:
            if val <= self.simtime_lims[0]:
                raise ValueError(
                    'simtime_total {} should be > step {}'.format(val,
                                                                  self.simtime_lims[
                                                                      0]))

        self._simtime_total = val

    @property
    def simtime_step(self):
        """
        The current time-step duration. While setting, the supplied value will
        be clipped to within :attr:`simtime_lims`.

        Returns:
            PhysicalField: in seconds

        """
        return self._simtime_step

    @simtime_step.setter
    def simtime_step(self, val):
        try:
            val = PhysicalField(val, 's')
        except TypeError:
            raise ValueError(
                'simtime_step {!r} not compatible with time units'.format(val))

        dtMin, dtMax = self.simtime_lims
        # val = min(max(val, dtMin), dtMax)
        val = min(val, dtMax)
        assert hasattr(val, 'unit')

        if self.simtime_total is not None:
            if self.simtime_total <= val:
                raise ValueError(
                    'simtime_total {} should be > step {}'.format(
                        self.simtime_total, val))

        self._simtime_step = val

    @property
    def simtime_lims(self):
        """
        The limits for the time-step duration allowed during evolution.

        This parameter determines the degree to which the simulation evolution
        can be speeded up. In phases of the model evolution where the numerical
        solution is reached within a few sweeps, the clock would run at the max
        limit, whereas when a large number of sweeps are required, it would be
        penalized towards the min limit.

        A high max value enables faster evolution, but can also lead to
        numerical inaccuracy ( higher residual) or solution breakdown (numerical
        error) during :meth:`.run_timestep`. A small enough min value allows
        recovery, but turning back the clock to the previous time step and
        restarting with the min timestep and allowing subsequent relaxation.

        Args:
            vals (float, PhysicalField): the (min, max) durations in seconds

        Returns:
            lims (tuple): The (min, max) limits of :attr:`simtime_step` each
            as a :class:`.PhysicalField`

        """

        return self._simtime_lims

    @simtime_lims.setter
    def simtime_lims(self, vals):
        if vals is None:
            lmin = PhysicalField(0.1, 's')
            # lmax = (self.simtime_total / 25.0).inUnitsOf('s').floor()
            lmax = PhysicalField(120, 's')
        else:
            lmin, lmax = [PhysicalField(float(_), 's') for _ in vals]
        if not (0 < lmin < lmax):
            raise ValueError(
                'simtime_lims ({}, {}) are not positive and in order'.format(
                    lmin, lmax))
        self._simtime_lims = (lmin, lmax)
        self.logger.debug('simtime_lims set: {}'.format(self._simtime_lims))

    @property
    def max_sweeps(self):
        """
        The maximum number of sweeps allowed for a timestep

        Args:
            val (int): should be > 0

        Returns:
            int

        """
        return self._max_sweeps

    @max_sweeps.setter
    def max_sweeps(self, val):
        try:
            val = int(val)
            assert val > 0
            self._max_sweeps = val
        except:
            raise ValueError('max_sweeps {} should be > 0'.format(val))

    @property
    def model(self) -> MicroBenthosModel:
        """
        The model to run the simulation on. This is typically an instance of
        :class:`~microbenthos.MicroBenthosModel` or its subclasses. The
        interface it must
        provide is:

            * a method :meth:`create_full_equation()`

            * an attribute :attr:`full_eqn` created by above method, which is a
              :class:`~fipy.terms.binaryTerm._BinaryTerm` that has a
              :meth:`sweep()` method.

            * method :meth:`model.update_vars()` which is called before each
            timestep

            * method :meth:`model.clock.increment_time(dt)` which is called
            after each timestep

        Additionally, if :attr:`.simtime_days` is set, then setting the model
        will try to find the ``"env.irradiance:`` object and use its
        :attr:`.hours_total` attribute to set the :attr:`.simtime_total`.

        Args:
            model (:class:`~microbenthos.MicroBenthosModel`): model instance

        Returns:
            :class:`~microbenthos.MicroBenthosModel`

        Raises:
            RuntimeError: if model has already been set
            ValueError: if modes interface does not match
            ValueError: if model :attr:`.model.full_eqn` does not get created
                even after :meth:`.model.create_full_equation` is called.

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
                'Model {!r} (type={}) does not have a valid equation'.format(
                    m, type(m)))

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
        expected_callables = ['full_eqn.sweep', 'update_vars',
                              'clock.increment_time']
        failed_attrs = tuple(
            filter(lambda x: not recursive_hasattr(m, x),
                   expected_attrs))
        failed_callables = tuple(
            filter(lambda x: not recursive_hasattr(m, x, is_callable=True),
                   expected_callables))

        if failed_attrs:
            self.logger.error(
                'Model is missing required attributes: {}'.format(failed_attrs))
        if failed_callables:
            self.logger.error('Model is missing required callables: {}'.format(
                failed_callables))

        if failed_callables or failed_attrs:
            raise ValueError(
                'Model interface is missing: {}'.format(
                    set(failed_attrs + failed_callables)))

        self._model = m

        # if simtime_days is given, override the simtime_total with it
        if self.simtime_days is not None:
            I = self.model.get_object('env.irradiance')
            simtime_total = self.simtime_days * I.hours_total
            self.logger.info(
                'Setting simtime_total={} for {} days of simtime'.format(
                    simtime_total, self.simtime_days
                    ))
            self.simtime_total = simtime_total

    def _create_solver(self):
        """
        Create the fipy solver to be used
        """
        solver_module = importlib.import_module(
            'fipy.solvers.{}'.format(self.fipy_solver))
        Solver = getattr(solver_module, 'DefaultSolver')
        self._solver = Solver()
        self.logger.debug(
            'Created fipy {} solver: {}'.format(self.fipy_solver, self._solver))

    def run_timestep(self):
        """
        Evolve the model through a single timestep
        """
        if not self.started:
            raise RuntimeError(
                'Simulation timestep cannot be run since started=False')

        if self.model is None:
            raise RuntimeError('Simulation model is None, cannot run timestep')

        dt = self.simtime_step
        self.logger.info(
            'Running timestep {} + {}'.format(self.model.clock, dt))

        num_sweeps = 0

        EQN = self.model.full_eqn
        retry = True

        res = 100.0

        while (res > self.max_residual) and (num_sweeps < self.max_sweeps) \
            and retry:

            try:
                res = EQN.sweep(
                    solver=self._solver,
                    dt=float(dt.numericValue)
                    )
                num_sweeps += 1
                res = float(res)
                self.logger.debug(
                    'Sweeps: {}  residual: {:.2g}'.format(num_sweeps, res))

            except (TypeError, RuntimeError):
                self.logger.warning(f'Error with simulation timestep dt={dt}')
                res = self.max_residual*100
                break

        return res, num_sweeps

    def evolution(self):
        """
        Evolves the model clock through the time steps for the simulation, i.e.
        by calling :meth:`.run_timestep` and :meth:`.model.clock.increment_time`
        repeatedly while ``model.clock() <= self.simtime_total``.

        This is a generator that yields the step number, and the state of the
        evolution after each time step. If :meth:`snapshot_due` is true, then
        also the model snapshot is included in the state.

        Yields:
            `(step, state)` tuple of step number and simulation state

        Raises:
            RuntimeError: if :attr:`.started` is already True

        """
        if self.started:
            raise RuntimeError(
                'Simulation already started. Cannot run parallel evolutions!')

        self.logger.debug(
            'simtime_total={o.simtime_total} simtime_step={o.simtime_step}, '
            'max_sweeps={o.max_sweeps} max_residual={o.max_residual}'.format(o=self))

        self.logger.debug('Solving: {}'.format(self.model.full_eqn))

        self._create_solver()
        self._started = True
        self.logger.info('Simulation evolution starting')

        self.model.update_vars()

        self._prev_snapshot = Variable(self.model.clock.copy(),
                                       name='prev_snapshot')
        step = 0
        self.simtime_step = self.simtime_lims[0]

        while self.model.clock() <= self.simtime_total:
            self.logger.debug(
                'Running step #{} {}'.format(step, self.model.clock))

            dt = self.simtime_step

            tic = time.time()
            residual, num_sweeps = self.run_timestep()
            toc = time.time()
            self.logger.debug(f'For dt={dt} residual={residual:.4g} with sweeps={num_sweeps}')

            if residual == 0:
                raise RuntimeError(f'Residual perfect 0 for dt={dt}. Problem in domain!')

            self._sweepsQ.appendleft(num_sweeps)
            self._residualQ.appendleft(residual)

            if residual >= self.max_residual:

                self.logger.info(f'Ignoring dt={dt}: res={residual:.4g} > {self.max_residual:.4g}')
                self.update_simtime_step(residual, num_sweeps)
                self.model.revert_vars()

                # just go back to while loop start, now that dt has been made smaller
                continue

            else:
                self.model.update_vars()
                self.model.update_equations(dt)

                step += 1

            self.update_simtime_step(residual, num_sweeps)

            calc_time = 1000 * (toc - tic)
            self.logger.debug('Time step {} done in {:.2f} msec'.format(
                self.simtime_step, calc_time))

            if self.snapshot_due():

                self.logger.debug('Snapshot in step #{}'.format(step))

                state = self.get_state(
                    state=self.model.snapshot(),
                    calc_time=calc_time,
                    residual=residual,
                    num_sweeps=num_sweeps
                    )

                yield (step, state)

                # now set the prev_snapshot so that snapshot_due() will
                # remain true for processing
                self._prev_snapshot.setValue(self.model.clock.copy())
                self.logger.debug(
                    'Prev snapshot set: {}'.format(self._prev_snapshot))

            else:
                # create a minimal state
                # this is the model clock and current residual
                state = self.get_state(
                    calc_time=calc_time,
                    residual=residual,
                    num_sweeps=num_sweeps
                    )

                yield (step, state)

            self.model.clock.increment_time(dt)

        self.logger.info('Simulation evolution completed')
        self._started = False

    def get_state(self, state = None, metrics = None, **kwargs):
        """
        Get the state of the simulation evolution

        Args:
            state (None, dict):
                If state is given (from ``model.snapshot()``), then that is used.
                If None, then just the time info is created by using
                :attr:`.model.clock`.

            metrics (None, dict):
                a dict to get the simulation metrics from,
                else from `kwargs`

            **kwargs:
                parameters to build metrics dict. Currently the keys
                `"calc_time"`, `"residual"` and `"num_sweeps"` are used,
                if available.

        Returns:
            dict: the simulation state

        """

        if state is None:
            state = dict(
                time=dict(data=snapshot_var(self.model.clock))
                )

        if metrics is None:
            metrics = dict(
                calc_time=dict(
                    data=(kwargs.get('calc_time', 0.0), dict(unit='ms'))
                    ),
                residual=dict(
                    data=(kwargs.get('residual', 0.0), None)),
                num_sweeps=dict(
                    data=(kwargs.get('num_sweeps', 0), None)),
                )

        state['metrics'] = metrics
        return state

    def snapshot_due(self):
        """
        Returns:
            bool: If the current model clock time has exceeded
            :attr:`.snapshot_interval` since the last snapshot time
        """
        return self.model.clock() - self._prev_snapshot() >= \
               self.snapshot_interval

    def update_simtime_step(self, residual, num_sweeps):
        """
        Update the :attr:`.simtime_step` to be adaptive to the current
        residual and sweeps.

        A multiplicative factor for the time-step is determined based on the
        number of sweeps and residual. If the `residual` is more than
        :attr:`.max_residual`, then the time-step is quartered. If not, it is
        boosted by up to double, depending on the `num_sweeps` and
        :attr:`.max_sweeps`. Once a new timestep is determined, it is limited to
        the time left in the model simulation.

        Args:
            residual (float): the residual from the last equation step
            num_sweeps (int): the number of sweeps from the last equation step

        """
        self.logger.info(
            'Updating step {} after {}/{} sweeps and {:.3g}/{:.3g} '
            'residual'.format(
                self.simtime_step, num_sweeps, self.max_sweeps, residual,
                self.max_residual
                ))

        old_step = self.simtime_step
        mult = 1.0

        if residual >= self.max_residual:
            mult = 0.5

        else:
            # if the last N simtime steps have produced residuals lesser than max, then boost the
            # timestep
            if all([r < self.max_residual for r in list(self._residualQ)]):
                mult = 1.25
            else:
                mult = 1.0

        new_step = self.simtime_step * max(0.01, mult)
        self.simtime_step = min(new_step,
                                self.simtime_total - self.model.clock())
        self.logger.info(f'Residual={residual} max={self.max_residual}')
        self.logger.info('Time-step update {} x {:.2g} = {}'.format(
            old_step, mult, self.simtime_step))

