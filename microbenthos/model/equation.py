import logging
from collections import namedtuple

import sympy as sp
from fipy import CellVariable, TransientTerm, PhysicalField, Variable, DiffusionTerm, \
    ImplicitSourceTerm
from fipy.tools import numerix as np
from microbenthos import ModelVariable, Process, snapshot_var, restore_var


class ModelEquation(object):
    """
    Class that handles the creation of partial differential equations for a transient variable of
    the model
    """

    def __init__(self, model, varpath, coeff = 1, track_budget = False):
        """
        Initialize the model equation for a given variable

        Args:
            model (:class:`~.model.MicroBenthosModel`): model this belongs to
            varpath (str): Model path of the equation variable (example: "env.oxygen")
            coeff (int, float): the coefficient for the transient term
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Initializing ModelEqn for: {!r}'.format(varpath))

        getter = getattr(model, 'get_object', None)
        if not callable(getter):
            self.logger.error('Supplied model ({}) has no "get_object" method'.format(type(model)))
            raise ValueError('Invalid model type supplied: {}'.format(type(model)))

        #: the model instance this equation belongs to
        self.model = model

        var = self.model.get_object(varpath)
        if isinstance(var, ModelVariable):
            var = var.var
        if not isinstance(var, CellVariable):
            raise ValueError('Var {!r} is {}, not CellVariable'.format(varpath, type(var)))

        #: the path (str) to the equation variable
        self.varpath = varpath
        #: The equation variable object (:class:`~microbenthos.entity.Variable`)
        self.var = var
        #: the name of :attr:`.var`
        self.varname = var.name
        self.logger.debug('Found variable: {!r}'.format(self.var))

        self._term_transient = None
        self._term_diffusion = None
        #: container (dict) of the formulae of the sources (sympy expressions)
        self.source_formulae = {}
        #: container (dict) of the expressions of the sources (fipy variable binOp)
        self.source_exprs = {}
        #: container (dict) of the fipy equation terms (explicit & implicit) of the sources
        self.source_terms = {}
        #: the coefficients in the equation for the sources
        self.source_coeffs = {}
        #: The additive sum of the values in :attr:`source_exprs`
        self.sources_total = None

        self.diffusion_def = ()
        """:type : (str, float)
        
        The model path to the diffussion coeff and a numeric coefficient to multiply in the equation
        """

        #: the fipy term that is used in the model full_eqn
        self.obj = None
        #: flag to indicate if the equation has been finalized
        self.finalized = False

        term = TransientTerm(var=self.var, coeff=coeff)
        self.logger.debug('Created transient term with coeff: {}'.format(coeff))
        #: The transient term of the equation: dv/dt
        self.term_transient = term

        #: namedtuple definition for tracked fields:
        #: ('time_step', 'var_expected', 'var_actual', 'sources_change', 'transport_change')
        self.Tracked = namedtuple('tracked_budget',
                                  ('time_step', 'var_expected', 'var_actual', 'sources_change',
                                   'transport_change')
                                  )
        #: a tuple of tracked values according to :attr:`.Tracked`
        self.tracked = self.Tracked(
            PhysicalField(0.0, 's'),
            0.0, 0.0, 0.0, 0.0)

        self._track_budget = None
        self.track_budget = track_budget

    def __repr__(self):
        return 'TransientEqn({})'.format(self.varname)

    def finalize(self):
        """
        Call this to setup the equation. Once this is called, no more terms can be added.

        This does::

            self.obj = self.term_transient == sum(self.RHS_terms)

        Raises:
            RuntimeError: if no :attr:`.term_transient` defined or no RHS terms defined
        """
        if self.finalized:
            self.logger.warning('Equation already finalized')
            return

        if self.term_transient is None:
            raise RuntimeError('Cannot finalize equation without transient term!')

        RHS_terms = self.RHS_terms
        if not RHS_terms:
            raise RuntimeError('Cannot finalize equation without right-hand side terms')

        if self.source_exprs:
            self.sources_total = sum(self.source_exprs.values())
            #: the additive sum of all the sources
        else:
            self.sources_total = PhysicalField(np.zeros_like(self.var), self.var.unit.name() + '/s')

        self.obj = self.term_transient == sum(self.RHS_terms)
        self.update_tracked_budget(PhysicalField(0.0, 's'))
        self.finalized = True
        self.logger.info('Final equation: {}'.format(self.obj))

    @property
    def term_transient(self):
        """
        The transient term for the equation

        Returns:
            Instance of :class:`fipy.TransientTerm`
        """
        return self._term_transient

    @term_transient.setter
    def term_transient(self, term):
        if self.term_transient is not None:
            raise RuntimeError('Transient term has already been set!')

        self._term_transient = term
        self.logger.info('Transient term set: {}'.format(term))

    def _get_term_obj(self, path):
        """
        Get the model object at the path and return a usable fipy type

        Args:
            path (str): dotted path in the model store

        Returns:
            Variable | :class:`fipy.terms.binaryTerm._BinaryTerm`

        """

        obj = self.model.get_object(path)
        if isinstance(obj, ModelVariable):
            expr = obj.var
        elif isinstance(obj, Variable):
            expr = obj
        elif isinstance(obj, Process):
            expr = obj

        return expr

    def _add_diffusion_term(self, coeff):
        """
        Add a linear diffusion term to the equation

        Args:
            coeff (int, float, term): Coefficient for diffusion term

        """
        if self.finalized:
            raise RuntimeError('Equation already finalized, cannot add terms')

        term = DiffusionTerm(var=self.var, coeff=coeff)
        self.logger.debug('Created implicit diffusion term with coeff: {!r}'.format(coeff))
        self.term_diffusion = term

    def add_diffusion_term_from(self, path, coeff):
        """
        Add diffusion term from the object path

        Args:
            path (str): Path to model store
            coeff (int, float): Multiplier coefficient for object

        Returns:
            Object stored on model store

        Raises:
            ValueError if object not found at path

        """
        self.logger.debug('Adding diffusion term from {!r}'.format(path))

        obj = self._get_term_obj(path)
        term = obj.as_term()

        self._add_diffusion_term(coeff=term * coeff)
        self.diffusion_def = (path, coeff)

    @property
    def term_diffusion(self):
        """
        The diffusion term for the equation

        Returns:
            Instance of :class:`fipy.DiffusionTerm`
        """
        return self._term_diffusion

    @term_diffusion.setter
    def term_diffusion(self, term):
        if self.term_diffusion is not None:
            raise RuntimeError('Diffusion term has already been set!')

        self._term_diffusion = term
        self.logger.info('Diffusion term set: {}'.format(term))

    def add_source_term_from(self, path, coeff = 1):
        """
        Add a source term from the model path

        Args:
            path (str): Path to model store
            coeff (int, float): coeff for source term

        Raises:
            ValueError if path does not point to an object
        """
        if self.finalized:
            raise RuntimeError('Equation already finalized, cannot add terms')

        self.logger.info('{} Adding source term from {!r}'.format(self, path))

        if not isinstance(coeff, (int, float)):
            raise ValueError('Source coeff should be int or float, not {}'.format(type(coeff)))

        if path in self.source_exprs:
            raise RuntimeError('Source term path already exists: {!r}'.format(path))

        obj = self.model.get_object(path)
        """:type: Process"""

        # expr = obj.evaluate()
        # self.logger.debug('Created source expr: {!r}'.format(expr))
        self.source_coeffs[path] = coeff

        full_expr = obj.as_term()
        self.source_exprs[path] = coeff * full_expr
        self.source_formulae[path] = coeff * obj.expr()
        var, S0, S1 = obj.as_source_for(self.varname)
        assert var is self.var, 'Got var: {!r} and self.var: {!r}'.format(var, self.var)
        if S1 is not 0:
            S1 = ImplicitSourceTerm(coeff=S1, var=self.var)
            term = S0 + S1
        else:
            term = S0

        self.source_terms[path] = term

        self.logger.debug('Created source {!r}: {!r}'.format(path, term))

    def as_symbolic(self):
        """
        Return a symbolic version (sympy) of the equation
        """
        var = sp.var(self.varname)
        t, z = sp.var('t z')
        Dcoeff = sp.sympify(self.diffusion_def[1])
        D = sp.symbols('D{}'.format(self.varname))

        transient = sp.Derivative(var, t)
        diffusive = D * Dcoeff * sp.Derivative(var, z, 2)
        sources = sum(self.source_formulae.values())

        return sp.Eq(transient, diffusive + sources)

    def as_latex_string(self):
        """
        Return a latex string of the equation through sympy
        """
        return sp.latex(self.as_symbolic())

    def as_pretty_string(self):
        """
        Return a pretty (unicode) string of the equation through sympy
        """
        return sp.pretty(self.as_symbolic())

    @property
    def RHS_terms(self):
        """
        The right hand side terms of the equation

        Returns:
            A list of terms, with the first one being :attr:`.term_diffusion`, followed by the
            values in :attr:`.source_terms`.
        """
        terms = []
        if self.term_diffusion:
            terms.append(self.term_diffusion)

        terms.extend(self.source_terms.values())
        return terms

    def snapshot(self, base = False):
        """
        Return a state dictionary of the equation, with the structure

            * "sources"
                * "metadata": source paths and coefficients
                * "data": the net rate of the combined sources

            * "diffusion"
                * metadata: dict(:attr:`.diffusion_def`)

            * "transient"
                * "metadata":
                    * :attr:`.varpath`: transient term coeff

            * "tracked_budget" (if :attr:`.track_budget` is `True`)
                * var_expected: data: integrated density of variable from tracked changes
                * var_actual: data: integrated density of variable
                * time_step: data: the time step duration
                * sources_change: data: integrated rate of combined sources over the time step
                * transport_change: data: change in variable quantity due to mass transport

            "metadata"
                * "variable": :attr:`.varpath`

        Returns:
            dict: A dictionary of the equation state

        Raises:
            RuntimeError: if the equation is not yet finalized

        """
        self.logger.debug('Snapshot of {!r}'.format(self))
        if not self.finalized:
            raise RuntimeError('{} not finalized. Cannot snapshot!'.format(self))

        if self.diffusion_def:
            diff_def = dict([self.diffusion_def])
        else:
            diff_def = dict()

        state = dict(
            diffusion=dict(metadata=diff_def),

            transient=dict(metadata={self.varpath: self.term_transient.coeff}),

            metadata=dict(
                variable=self.varpath,
                ),

            sources=dict(
                metadata=self.source_coeffs,
                data=snapshot_var(self.sources_total, base=base)
                ),
            )

        if self.track_budget:
            tracked_state = {k: dict(data=snapshot_var(v, base=base)) for \
                             (k, v) in self.tracked._asdict().items()
                             }
            # tracked_state['var_actual'] = dict(data=snapshot_var(self.var_quantity(), base=base))
            state['tracked_budget'] = tracked_state

        return state

    def restore_from(self, state, tidx):
        """
        If "tracked_budget" is in the `state`, then set the values on the instance
        """

        self.logger.debug('Restoring {} from state: {}'.format(self, tuple(state)))

        # update the tracked budget info
        # self.Tracked = namedtuple('tracked_budget',
        #                           ('time_step', 'var_expected', 'var_actual', 'sources_change',
        #                            'transport_change')
        if not 'tracked_budget' in state:
            return

        tracked_state = state['tracked_budget']
        values = []
        for fld in self.tracked._fields:
            self.logger.debug('Reading tracked field {!r}'.format(fld))
            values.append(restore_var(tracked_state[fld], tidx))

        self.tracked = self.Tracked(*values)
        self.logger.debug('Restored {} budget: {}'.format(self, self.tracked))

    def sources_rate(self):
        """
        Estimate the rate of change of the variable quantity caused by source
        terms.

        Returns:
            PhysicalField: The integrated quantity of the sources

        """
        self.logger.debug('Estimating rate from {} sources '.format(len(self.source_terms)))

        # the total sources contribution
        if self.sources_total is not None:
            depths = self.model.domain.depths
            sources_rate = np.trapz(self.sources_total.numericValue, depths.numericValue)
            # the trapz function removes all units, so figure out the unit
            source_total_unit = (self.sources_total[0] * depths[0]).inBaseUnits().unit
            sources_rate = PhysicalField(sources_rate, source_total_unit)
            self.logger.debug('Calculated source rate: {}'.format(sources_rate))
        else:
            sources_rate = 0.0

        return sources_rate

    def transport_rate(self):
        """
        Estimate the rate of change of the variable quantity caused by transport
        at the domain boundaries

        Returns:
            PhysicalField: The integrated quantity of the transport rate

        """
        self.logger.debug('Estimating transport rate at boundaries')

        # the total transport at the boundaries
        # from Fick's law: J = -D dC/dx

        if self.term_diffusion:
            depths = self.model.domain.depths

            D = self.term_diffusion.coeff[0]

            top = -D[1] * (self.var[0] - self.var[1]) / (depths[1] - depths[0])
            bottom = -D[-2] * (self.var[-1] - self.var[-2]) / (depths[-1] - depths[-2])
            transport_rate = (top + bottom).inBaseUnits()
            # self.logger.debug('Calculated transport rate: {}'.format(transport_rate))

        else:
            transport_rate = 0.0

        return transport_rate

    def var_quantity(self):
        """
        Calculate the integral quantity of the variable in the domain

        Returns:
            PhysicalField: depth integrated amount
        """
        # self.logger.debug('Calculating actual var quantity')
        q = np.trapz(self.var.numericValue, self.model.domain.depths.numericValue)
        unit = (self.var[0] * self.model.domain.depths[0]).inBaseUnits().unit
        return PhysicalField(q, unit)

    def update_tracked_budget(self, dt):
        """
        Update the tracked quantities for the variable, sources and transport

        Args:
            dt (PhysicalField): the time step

        Note:
            This is not a very accurate way to measure it, because the boundaries conditions keep
            the value at the domain boundaries constant, and so is not a true measure of the
            equation change in the time step. However, it should provide an order of magnitude
            metric for the accuracy of the numerical approximation in solving the equation.

        """
        if not self.track_budget:
            return

        self.logger.debug("{}: Updating tracked budget".format(self))

        # the change in the domain for this time step is then:
        # (source - transport) * dt
        sources_change = dt * self.sources_rate()
        transport_change = dt * self.transport_rate()

        self.logger.debug('source change: {}  transport_change: {}'.format(
            sources_change, transport_change
            ))
        net_change = sources_change + transport_change
        var_expected = self.tracked.var_expected + net_change

        self.tracked = self.tracked._replace(
            time_step=dt,
            var_expected=var_expected,
            var_actual=self.var_quantity(),
            sources_change=sources_change,
            transport_change=transport_change
            )

        self.logger.debug('{}: Updated tracked: {}'.format(self, self.tracked))

    @property
    def track_budget(self):
        """
        Flag to indicate if the variable quantity should be tracked.

        When this is set, the variable quantity in the domain is :attr:`.tracked` through
        :meth:`.update_tracked_budget`.

        Returns:
            bool: Flag state

        """
        return self._track_budget

    @track_budget.setter
    def track_budget(self, b):
        b = bool(b)
        if b and self.track_budget:
            self.logger.debug('track_budget already set. Doing nothing.')
            return

        elif b and not self.track_budget:
            self.logger.debug("track_budget being set. Estimating quantities.")

            self.tracked = self.Tracked(
                time_step=0.0,
                var_expected=self.var_quantity(),
                var_actual=self.var_quantity(),
                sources_change=self.sources_rate(),
                transport_change=self.transport_rate()
                )

            self.logger.debug('Started tracking budget: {}'.format(self.tracked))

            self._track_budget = b

        elif not b:
            self.logger.debug('Resetting track budget')

            self.tracked = self.Tracked(0.0, 0.0, 0.0, 0.0, 0.0)

            self._track_budget = b
