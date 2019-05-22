import logging
from collections.abc import Mapping

import sympy as sp
from fipy.tools import numerix as np

from .expression import Expression
from ..core import DomainEntity
from ..utils import snapshot_var


class Process(DomainEntity):
    """
    Class to represent a reaction occurring in the model domain.

    It is used as an adapter to the symbolic formulation in :class:`Expression` into the model
    equation terms. By calling :meth:`.evaluate` the symbolic expression, is cast into
    :mod:`fipy` terms which can be used as :class:`fipy.SourceTerm` in the model. Additionally,
    if :attr:`.implicit` is set, then the expression will attempted to be cast into a linear and
    implicit source term which can help the speed of numerical approximation.

    """

    _lambdify_modules = (np, 'numpy')

    def __init__(self, expr,
                 params = None,
                 implicit = True,
                 events = None,
                 **kwargs):
        """
        Initialize the process

        Args:
            expr (dict, :class:`Expression`): input for :attr:`.expr` of the process

            params (dict): mapping of symbolic vars to numerical values uses in expression,
                typically to represent process parameters or constants.

            implicit (bool): Whether to cast the equation as implicit source term (default: True)

            events (None, dict): definitions for :meth:`.add_event`

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(Process, self).__init__(**kwargs)

        self._expr = None
        self.expr = expr
        assert isinstance(self.expr, Expression)

        params = params or {}
        #: the container (dict) for the parameters uses to :meth:`.evaluate` the process
        self.params = dict(params)
        self.logger.debug('{}: stored params: {}'.format(self, self.params))

        #: flag which controls if expression will be cast into linearized and implicit source terms
        self.implicit = implicit

        #: container (dict) of :class:`ProcessEvent`
        self.events = {}
        if events:
            for name, eventdef in events.items():
                self.add_event(name, **eventdef)

    @property
    def expr(self):
        """
        The symbolic expression of the mathematical formulation

        Args:
            e (dict, :class:`Expression`): if a dict, then it is passed to
                :meth:`Expression.__init__` with `name = self.name` to create the instance.

        Returns:
            :class:`Expression`

        """
        return self._expr

    @expr.setter
    def expr(self, e):
        if isinstance(e, Mapping):
            self.logger.debug('Creating expression instance from dict: {}'.format(e))
            e = Expression(name=self.name, **e)

        if not isinstance(e, Expression):
            raise ValueError('Need an Expression but got {}'.format(type(e)))

        self._expr = e

    def evaluate(self, expr, params = None, domain = None):
        """
        Evaluate the given sympy expression on the supplied domain and param containers.

        If `domain` is not given, then the :attr:`~DomainEntity.domain` is used. If `params` is not
        given, then :attr:`.params` is used.

        The `expr` atoms are inspected, and all symbols collected. Symbols that are not found in
        the `params` container, are set as variables to be sourced from the `domain`  or
        :attr:`.events` container.

        The symbols from the expression are collected, the expression lambdified and then
        evaluated using the objects sourced from the containers and events.

        Args:
            expr (int, :class:`~sympy.core.expr.Expr`): The expression to evaluate
            params (dict, None): The parameter container
            domain (dict, None): The domain container for variables

        Returns:
            evaluated result typically one of (:class:`fipy binOp`, :class:`numpy.ndarray`)

        """
        self.logger.debug('Evaluating expr {!r}'.format(expr))

        if not domain:
            self.check_domain()
            domain = self.domain

        if not params:
            params = self.params

        expr_symbols = filter(lambda a: isinstance(a, sp.Symbol), expr.atoms())
        param_symbols = tuple(sp.symbols(tuple(params.keys())))

        event_name_symbols = tuple(sp.symbols(tuple(self.events.keys())))
        var_symbols = tuple(set(expr_symbols).difference(
            set(param_symbols).union(set(event_name_symbols))))
        # self.logger.debug('Params available: {}'.format(param_symbols))
        # self.logger.debug('Vars to come from domain: {}'.format(var_symbols))
        allsymbs = var_symbols + param_symbols + event_name_symbols

        args = []
        for symbol in allsymbs:
            name_ = str(symbol)
            if symbol in var_symbols:
                args.append(domain[name_])

            elif symbol in param_symbols:
                param = params[name_]
                if hasattr(param, 'unit'):
                    # convert fipy.PhysicalField to base units
                    param = param.inBaseUnits()

                args.append(param)

            elif symbol in event_name_symbols:
                event = self.events[name_]
                # assert isinstance(event, ProcessEvent)
                args.append(event.event_time)

            else:
                raise RuntimeError('Unknown symbol {!r} in args list'.format(symbol))

        # self.logger.debug('Lambdifying with args: {}'.format(allsymbs))
        expr_func = sp.lambdify(allsymbs, expr, modules=self._lambdify_modules)

        self.logger.debug('Evaluating with {}'.format(zip(allsymbs, args)))
        return expr_func(*args)

    def as_source_for(self, varname, **kwargs):
        """
        Cast the :attr:`.expr` as a source condition for the given variable name.

        If :attr:`.implicit` is True, then the expression will be differentiated (symbolically)
        with respect to variable `v` (from `varname`), and the source expression `S` will be
        attempted to be split as `S1 = dS/dv` and `S0 = S - S1 * v` (see `fipy docs`_).

        If :attr:`.implicit` is False, then returns `(S,0)`. This also turns out to be the case
        when the expression `S` is linear with respect to the variable `v`.

        Finally `S0` and `S1` are evaluated and returned.

        Args:
            varname (str): The variable that the expression is a source for
            coeff (int, float): Multiplier for the terms
            kwargs (dict): Keyword arguments forwarded to :meth:`.evaluate`

        Returns:
            tuple: A `(varobj, S0, S1)` tuple, where `varobj` is the variable evaluated on the
                domain, and `S0` and `S1` are the evaluated source expressions on the domain. If
                `S1` is non-zero, then it indicates it should be cast as an implicit source.

        .. _fipy docs: https://www.ctcms.nist.gov/fipy/examples/phase/generated/examples.phase
            .simple.html

        """
        self.logger.debug('{}: creating as source for variable {!r}'.format(self, varname))

        var = sp.symbols(varname)
        varobj = self.evaluate(var, **kwargs)

        if var not in self.expr.symbols():
            S0 = self.expr.expr()
            S1 = 0

        else:
            S = self.expr.expr()

            if self.implicit:
                self.logger.debug('Attempting to split into implicit component')
                S1 = self.expr.diff(var)
                S0 = S - S1 * var
                self.logger.debug('Got S1 {}: {}'.format(type(S1), S1))

                if var in S1.atoms():
                    self.logger.debug(
                        'S1 dependent on {}, so should be implicit condition'.format(var))

                else:
                    S0 = S
                    S1 = 0

            else:
                S0 = S
                S1 = 0

        self.logger.debug('Source S0={}'.format(S0))
        self.logger.debug('Source S1={}'.format(S1))

        self.logger.debug('Evaluating S0 and S1 now')
        S0term = self.evaluate(S0, **kwargs)
        if S1:
            S1term = self.evaluate(S1, **kwargs)
        else:
            S1term = 0

        return (varobj, S0term, S1term)

    def as_term(self, **kwargs):
        """
        Return the process as :mod:`fipy` term by calling :meth:`.evaluate`
        """
        return self.evaluate(self.expr.expr(), **kwargs)

    def repr_pretty(self):
        """
        Return a pretty representation of the :attr:`.expr`.

        See :func:`~sympy.printing.pretty.pretty.pretty`

        """
        e = self.expr.expr()
        return sp.pretty(e)

    def snapshot(self, base = False):
        """
        Returns a snapshot of the state with the structure

            * "metadata"

                * "expr" : str(`.expr.expr()`)

                * "param_names": tuple(:attr:`.params`)

                * name: str(p) for p in :attr:`.params`

            * "data" : (:func:`.snapshot_var` of :meth:`.as_term`)

        Args:
            base (bool): Convert to base units?

        Returns:
            dict: the process state

        """
        self.check_domain()
        self.logger.debug('Snapshot: {}'.format(self))

        state = dict()
        meta = state['metadata'] = {}
        meta['expr'] = str(self.expr.expr())
        meta['param_names'] = tuple(self.params.keys())
        for p, pval in self.params.items():
            meta[p] = str(pval)

        evaled = self.as_term()

        state['data'] = snapshot_var(evaled, base=base)

        return state

    def restore_from(self, state, tidx):
        """
        Restore the process state. This is a no-op as the term of the process is symbolically
        defined through :class:`fipy.binOp`.
        """
        self.logger.debug('Restoring {} from state: {}'.format(self, tuple(state)))
        self.check_domain()

        # nothing to restore here since evaled = as_term() is a binary operator of other variables
        pass

    def add_event(self, name, **definition):
        """
        Add an event to this process through :class:`ProcessEvent`

        Args:
            name (str): Name for the event
            definition (dict): definition for the event

        Returns:

        """
        self.logger.debug('{}: creating event {!r}'.format(self, name))
        definition['name'] = name
        event = ProcessEvent(**definition)
        self.events[name] = event
        self.logger.info('Added event: {}'.format(event))

    def setup(self, **kwargs):
        """
        Sets up any contained :attr:`.events`
        """
        for event in self.events.values():
            event.setup(process=self, **kwargs)

    def on_time_updated(self, clocktime):
        """
        Updates any contained :attr:`.events`
        """
        for event in self.events.values():
            event.on_time_updated(clocktime)


class ProcessEvent(DomainEntity):
    """
    Class that represents a temporal event in the domain. Events are useful for tracking the last
    time at which a certain condition occurred in the domain.


    It is represented as a relational expression between different domain variables. When this
    relation is True, then the time of the event is considered active at that domain depth
    location. The event time tracks the duration for which the event relation is True. This can
    be used to model inductive processes in microbial groups, where a certain amount of time is
    necessary after conditions are met for the metabolic activity to begin.
    """

    def __init__(self, expr, **kwargs):
        """
        Create the process event by specifying a symbolic expression for the relation between
        domain variables.

        Args:
            expr (dict, :class:`Expression`): The relational expression between domain variables
                in symbolic form

        Example:
            * "oxy >= OxyThreshold"
            * "(oxy > oxyMin) & (light > lightMin)"

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(ProcessEvent, self).__init__(**kwargs)

        self.logger.debug('Creating event {!r}: {}'.format(self.name, expr))

        self.expr = expr

        #: The process that this event belongs to
        self.process = None

        #: The depth distribution of the time when the event condition was reached
        self.event_time = None

        #: The event condition expressed through domain variables
        self.condition = None

        self._prev_clock = None

    def __repr__(self):
        if self.process:
            return '{}:Event({})'.format(
                # self.__class__.__name__,
                self.process.name,
                self.name
                )
        else:
            return super(ProcessEvent, self).__repr__()

    @property
    def expr(self):
        """
        Similar to :attr:`Process.expr`
        """
        return self._expr

    @expr.setter
    def expr(self, e):
        if isinstance(e, Mapping):
            self.logger.debug('Creating expression instance from dict: {}'.format(e))
            if not e.get('name'):
                e['name'] = self.name
            e = Expression(**e)

        if not isinstance(e, Expression):
            raise ValueError('Need an Expression but got {}'.format(type(e)))

        self._expr = e

    def setup(self, process, model, **kwargs):
        """
        Setup the event time variable that contains the duration since when the event condition
        was reached at each depth location. The event condition is created by using
        :meth:`~Process.evaluate`.

        Args:
            process (:class:`Process`): The process this event belongs to
            model (:class:`MicroBenthosModel`): The model instance

        """
        self.logger.debug('Setting up {} with {}'.format(self, process))
        self.process = process

        self.event_time = model.domain.create_var(
            name=repr(self),
            store=False,
            unit='s',
            value=model.clock
            )
        self._prev_clock = model.clock.copy()
        self.logger.debug('Clock set to: {}'.format(self._prev_clock))
        self.condition = self.process.evaluate(self.expr.expr())

    def on_time_updated(self, clock):
        """
        The event_time must be reset, wherever :attr:`.condition` evaluates to False. Wherever it
        evaluates to True, then increment the value by ``(clock - prev_clock)``.
        """
        self.logger.debug('Updating {} to clock {}'.format(self, clock))
        dt = clock.copy() - self._prev_clock
        self.logger.debug('Time since last: {}'.format(dt.inUnitsOf('s')))
        condition = self.condition()
        self.event_time.setValue(self.event_time.copy() + dt)
        self.event_time.value[~condition] = 0.0
        self._prev_clock = clock.copy()

        self.logger.debug('{} condition true in {} of {} with max time: {}'.format(
            self,
            np.count_nonzero(condition),
            len(condition),
            max(self.event_time)
            ))
