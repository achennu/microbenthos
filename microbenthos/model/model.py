import logging
from collections import Mapping
from fipy import TransientTerm, ImplicitDiffusionTerm, ImplicitSourceTerm, CellVariable, Variable, \
    PhysicalField
from sympy import Lambda, symbols

from ..core import Entity, ExprProcess, SedimentDBLDomain
from ..core import Variable as mVariable
from ..utils import snapshot_var, CreateMixin


class MicroBenthosModel(CreateMixin):
    """
    Class that represents the model, as a container for all the entities in the domain
    """
    schema_key = 'model'
    def __init__(self, **kwargs):
        super(MicroBenthosModel, self).__init__()
        # the __init__ call is deliberately empty. will implement cooeperative inheritance only
        # when necessary
        self.logger = logging.getLogger(__name__)
        self.logger.info('Initializing {}'.format(self.__class__.__name__))

        self._domain = None
        self.microbes = {}
        self.env = {}
        self.full_eqn = None
        self.source_exprs = {}
        self.equations = {}

        # self.domain = domain

        self.clock = ModelClock(self, value=0.0, unit='h', name='time')

        self._setup(**kwargs)

    def add_formula(self, name, variables, expr):
        """
        Add a formula to the model namespace

        Example:
            name = optimum_response
            variables = (x, Ks, Ki)
            expr = x / (x + Ks) / (1 + x/Ki)

        Args:
            name (str): Name of the formula
            variables (list): Variables in the formula expression
            expr (str): The expression to be parsed by sympy

        Returns:

        """
        self.logger.info('Adding formula {!r}: {}'.format(name, expr))

        func = Lambda(symbols(variables), expr)
        self.logger.debug('Formula {!r}: {}'.format(name, func))
        ExprProcess._sympy_ns[name] = func

    @property
    def domain(self):
        """
        The model domain
        """
        return self._domain

    @domain.setter
    def domain(self, domain):

        if domain is None:
            return

        if self.domain is not None:
            raise RuntimeError('Model domain has already been set!')

        self._domain = domain

    def create_entity_from(self, defdict):
        """
        Create a model entity from dictionary, and set it up with the model and domain.

        Returns:
            The entity created
        """
        self.logger.debug('Creating entity from {}'.format(defdict))
        entity = Entity.from_dict(defdict)
        entity.set_domain(self.domain)
        entity.setup(model=self)
        assert entity.check_domain()
        return entity

    def _create_entity_into(self, target, name, defdict):
        """
        Create an entity from its definition dictionary and store it into the target dictionary

        Args:
            target (str): Target dict such as env, microbes
            name (str): The key for the dictionary
            defdict (dict): Parameter definition of the entity

        """
        tdict = getattr(self, target)
        if name in tdict:
            self.logger.warning("Entity {!r} exists in {}! Overwriting!".format(name, target))
        entity = self.create_entity_from(defdict)
        self.logger.info('Adding {} entity {} = {}'.format(target, name, entity))
        tdict[name] = entity

    # @classmethod
    # def _from_definition(cls, definition):
    def _setup(self, **definition):
        """
        Create a model instance from the definition dictionary, which is assummed to be validated

        Returns:
            instance of :class:`MicrobenthosModel`


        """
        self.logger.debug('Setting up model from definition: {}'.format(definition.keys()))

        domain_def = definition.get('domain')
        if domain_def:
            self.logger.warning('Creating the domain')
            self.logger.debug(domain_def)
            if isinstance(domain_def, Mapping):
                self.domain = Entity.from_dict(domain_def)
            elif isinstance(domain_def, SedimentDBLDomain):
                self.domain = domain_def

        # Load up the formula namespace
        if 'formulae' in definition:
            self.logger.warning('Creating formulae')
            for name, fdict in definition['formulae'].items():
                self.add_formula(name, **fdict)

        env_def = definition.get('environment')
        if env_def:
            self.logger.warning('Creating environment')

            for name, pdict in env_def.items():
                self._create_entity_into('env', name, pdict)

        microbes_def = definition.get('microbes')
        if microbes_def:
            self.logger.warning('Creating microbes')

            for name, pdict in microbes_def.items():
                self._create_entity_into('microbes', name, pdict)

        if not self.all_entities_setup:
            self.entities_setup()

        eqndef = definition.get('equations')
        if eqndef:
            self.logger.warning('Creating equations')
            for eqnname, eqndef in eqndef.items():
                self.add_equation(eqnname, **eqndef)

        if self.equations:
            self.create_full_equation()

        self.logger.info('Model setup done')

    # @classmethod
    # def from_yaml(cls, stream, **kwargs):
    #     """
    #     Load definition from YAML stream and create instance. See :meth:`from_yaml` for arguments.
    #     """
    #     if kwargs.get('schema') is None:
    #         kwargs['key'] = 'model'
    #     return MicroBenthosModel._from_definition(
    #         from_yaml(stream, **kwargs))
    #
    # @classmethod
    # def from_dict(cls, mdict, **kwargs):
    #     """
    #     Load definition from dict and create instance. See :meth:`from_dict` for
    #             arguments.
    #             """
    #     if kwargs.get('schema') is None:
    #         kwargs['key'] = 'model'
    #     return MicroBenthosModel._from_definition(
    #         from_dict(mdict, **kwargs))

    def entities_setup(self):
        """
        Check that the model entities are setup fully, if not attempt it.
        """
        for entity in self.env.values() + self.microbes.values():
            if not entity.is_setup:
                self.logger.info('Setting up dangling entity: {!r}'.format(entity))
                entity.setup(model=self)

    @property
    def all_entities_setup(self):
        """
        Flag that indicates if all entities have been setup
        """
        return all([e.is_setup for e in self.env.values() + self.microbes.values()])

    def snapshot(self, base = False):
        """
        Create a snapshot of the model state.

        This method recursively calls the :meth:`snapshot` method of all contained entities,
        and compiles them into a nested dictionary. The dictionary has the structure of the
        model, except that that two reserved keys `data` and `metadata` indicate the presence of
        a numeric array or the metadata for the corresponding entity. This should be useful to
        parse this for serialization in hierarchical formats (like :mod:`h5py`) or flat formats
        by de-nesting as required. In the latter case, disambiguation of identically named variables
        will have to be performed first. Each snapshot, should be possible to plot out
        graphically as it contains all the metadata associated with it.

        Args:
            base (bool): Whether the entities should be converted to base units?

        Returns:
            A dictionary of the model state (domain, env, microbes)
        """
        self.logger.debug('Creating model snapshot')
        state = {}
        state['time'] = dict(data=snapshot_var(self.clock))
        state['domain'] = self.domain.snapshot(base=base)

        env = state['env'] = {}
        microbes = state['microbes'] = {}
        for name, obj in self.env.items():
            self.logger.debug('Snapshotting: {} --> {}'.format(name, obj))
            ostate = obj.snapshot(base=base)
            env[name] = ostate

        for name, obj in self.microbes.items():
            self.logger.debug('Snapshotting: {} --> {}'.format(name, obj))
            ostate = obj.snapshot(base=base)
            microbes[name] = ostate

        eqns = state['equations'] = {}
        for name, obj in self.equations.items():
            self.logger.debug('Snapshotting: {} --> {}'.format(name, obj))
            ostate = obj.snapshot()
            eqns[name] = ostate

        self.logger.debug('Created model snapshot')
        return state

    __getstate__ = snapshot

    def add_equation(self, name, transient, sources = None, diffusion = None):
        """
        Create a transient equation for the model.

        The term definitions are provided as `(model_path, coeff)` pairs to be created for the
        transient term, diffusion term and source terms.

        Args:
            name (str): Identifier for the equation
            transient (tuple): Single definition for transient term
            sources (list): A list of definitions for source terms
            diffusion (tuple): Single definition for diffusion term

        Returns:
            an instance of a finalized :class:`ModelEquation`

        """
        self.logger.debug(
            'Creating equation for transient={}, diffusion={} and sources={}'.format(transient,
                                                                                     diffusion,
                                                                                     sources))
        if name in self.equations:
            raise RuntimeError('Equation with name {!r} already exists!'.format(name))

        def is_pair_tuple(obj):
            try:
                path, coeff = obj
                return True
            except:
                return False

        if not is_pair_tuple(transient):
            raise ValueError('Transient term must be a (path, coeff) tuple!')

        if not (diffusion) and not (sources):
            raise ValueError('One or both of diffusion and source terms must be given.')

        if diffusion:
            if not is_pair_tuple(diffusion):
                raise ValueError('Diffusion term must be a (path, coeff) tuple')

        if sources:
            improper = filter(lambda x: not is_pair_tuple(x), sources)
            if improper:
                raise ValueError('Source terms not (path, coeff) tuples: {}'.format(improper))

        eqn = ModelEquation(self, *transient)
        if diffusion:
            eqn.add_diffusion_term_from(*diffusion)

        if sources:
            for source_path, source_coeff in sources:
                eqn.add_source_term_from(source_path, source_coeff)

        eqn.finalize()

        self.logger.info('Adding equation {!r}'.format(name))
        self.equations[name] = eqn

    def create_full_equation(self):
        """
        Create the full model equation by coupling the individual equations, and collect the
        source expressions.

        Returns: an equation solvable by fipy
        """
        if not self.equations:
            raise RuntimeError('No equations available for model!')

        self.logger.info('Creating full equation from {}'.format(self.equations.keys()))

        import operator

        full_eqn = reduce(operator.and_, [eqn.obj for eqn in self.equations.values()])
        self.logger.info('Full model equation: {!r}'.format(full_eqn))

        self.full_eqn = full_eqn

        self.logger.debug('Collecting unique source term expressions')
        for eqn in self.equations.values():

            for name, expr in eqn.source_exprs.items():

                if name not in self.source_exprs:
                    self.source_exprs[name] = expr

                else:
                    old = self.source_exprs[name]
                    if old is not expr:
                        raise RuntimeError(
                            'Another source with same name {!r} exists from different '
                            'equation!'.format(
                                name))

    def get_object(self, path):
        """
        Get an object stored in the model

        Args:
            path (str): The stored path for the object in the model

        Returns:
            The stored object if found

        Raises:
            ValueError if no object found at given path
        """
        self.logger.debug('Getting object {!r}'.format(path))
        parts = path.split('.')

        if len(parts) == 1:
            raise ValueError('Path should dotted string, but got {!r}'.format(path))

        S = self
        for p in parts:
            self.logger.debug('Getting {!r} from {}'.format(p, S))
            S_ = getattr(S, p, None)
            if S_ is None:
                try:
                    S = S[p]
                except (KeyError, TypeError):
                    raise ValueError(
                        'Unknown model path {!r}'.format('.'.join(parts[:parts.index(p)])))
            else:
                S = S_

        obj = S
        self.logger.debug('Got obj: {!r}'.format(obj))
        return obj

    def on_time_updated(self):
        """
        Callback function to update the time on all the stored entities
        """
        self.logger.info('Updating entities for model clock: {}'.format(self.clock))

        for name, obj in self.env.items():
            obj.on_time_updated(self.clock)

        for name, obj in self.microbes.items():
            obj.on_time_updated(self.clock)

    def update_vars(self):
        """
        Update all stored variables which have an `hasOld` setting. This is used while sweeping
        for solutions.
        """
        self.logger.debug('Updating model variables with hasOld')
        updated = []
        for name, obj in self.env.items():
            path = 'env.{}'.format(name)
            if isinstance(obj, mVariable):
                try:
                    obj.var.updateOld()
                    self.logger.debug("Updated old: {}".format(path))
                    updated.append(path)
                except AssertionError:
                    self.logger.debug('{} = {!r}.var.updateOld failed'.format(path, obj))

            else:
                self.logger.debug('env.{!r} not model variable'.format(obj))

        for name, microbe in self.microbes.items():
            for fname, feat in microbe.features.items():
                path = 'microbes.{}.features.{}'.format(name, fname)
                if isinstance(feat, mVariable):
                    try:
                        feat.var.updateOld()
                        self.logger.debug("Updated old: {}".format(path))
                        updated.append(path)
                    except AssertionError:
                        self.logger.debug('{} = {!r}.var.updateOld failed'.format(path, obj))
                else:
                    self.logger.debug(
                        '{}={!r} is not model variable'.format(path, obj))

        return updated


class ModelEquation(object):
    """
    Class that handles the creation of partial differential equations for a transient variable of
    the model
    """

    def __init__(self, model, varpath, coeff = 1):
        """
        Initialize the model equation for a given variable

        Args:
            model (object): an instance of :class:`MicroBenthosModel`
            varpath (str): Model path of the equation variable
            coeff (int, float): the coefficient for the transient term
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Initializing ModelEqn for: {!r}'.format(varpath))

        getter = getattr(model, 'get_object', None)
        if not callable(getter):
            self.logger.error('Supplied model ({}) has no "get_object" method'.format(type(model)))
            raise ValueError('Invalid model type supplied: {}'.format(type(model)))

        self.model = model

        var = self.model.get_object(varpath)
        if isinstance(var, mVariable):
            var = var.var
        if not isinstance(var, CellVariable):
            raise ValueError('Var {!r} is {}, not CellVariable'.format(varpath, type(var)))

        self.varpath = varpath
        self.var = var
        self.varname = var.name
        self.logger.debug('Found variable: {}'.format(self.var))

        self._term_transient = None
        self._term_diffusion = None
        self.source_exprs = {}
        self.source_terms = {}
        self.source_coeffs = {}

        self.diffusion_def = ()

        self.obj = None
        self.finalized = False

        term = TransientTerm(var=self.var, coeff=coeff)
        self.logger.debug('Created transient term with coeff: {}'.format(coeff))
        self.term_transient = term

    def __repr__(self):
        return 'TransientEqn({})'.format(self.varname)

    def finalize(self):
        """
        Call this to setup the equation object. Once this is called, no more terms can be added.

        Raises:
            RuntimeError: if no :attr:`term_transient` defined or no RHS terms defined
        """
        if self.finalized:
            self.logger.warning('Equation already finalized')
            return

        if self.term_transient is None:
            raise RuntimeError('Cannot finalize equation without transient term!')

        RHS_terms = self.RHS_terms
        if not RHS_terms:
            raise RuntimeError('Cannot finalize equation without right-hand side terms')

        self.obj = self.term_transient == sum(self.RHS_terms)
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

    def _add_diffusion_term(self, coeff):
        """
        Add a linear diffusion term to the equation

        Args:
            coeff (int, float, term): Coefficient for diffusion term

        """
        if self.finalized:
            raise RuntimeError('Equation already finalized, cannot add terms')

        term = ImplicitDiffusionTerm(var=self.var, coeff=coeff)
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

        obj = self.model.get_object(path)
        expr = obj.evaluate()
        self._add_diffusion_term(coeff=expr * coeff)
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
            coeff (int, float): coeff for source expr object

        Returns:
            None

        Raises:
            ValueError if path does not point to an object
        """
        if self.finalized:
            raise RuntimeError('Equation already finalized, cannot add terms')

        self.logger.info('Adding source term from {!r}'.format(path))

        if not isinstance(coeff, (int, float)):
            raise ValueError('Source coeff should be int or float, not {}'.format(type(coeff)))

        obj = self.model.get_object(path)
        # this is an ExprProcess instance

        # if not isinstance(obj, ExprProcess):
        #     raise NotImplementedError('Source term from type: {!r}'.format(type(obj)))

        expr = obj.evaluate()
        self.logger.debug('Created source expr: {!r}'.format(expr))

        if path in self.source_exprs:
            raise RuntimeError('Source term path already exists: {!r}'.format(path))

        self.source_exprs[path] = expr

        # check if it should be an implicit source

        dvars = obj.dependent_vars()
        ovars = dvars.difference({self.varname})
        is_implicit = bool(ovars)
        if is_implicit:
            self.logger.debug('Making implicit because of other vars: {}'.format(ovars))
            term = ImplicitSourceTerm(coeff=coeff * expr, var=self.var)

        else:
            term = coeff * expr

        self.source_terms[path] = term
        self.source_coeffs[path] = coeff
        self.logger.info('Created source {!r}: {!r}'.format(path, term))

    @property
    def RHS_terms(self):
        """
        The right hand side terms of the equation

        Returns:
            A list of terms, with the first one being diffusion term
        """
        terms = []
        if self.term_diffusion:
            terms.append(self.term_diffusion)

        terms.extend(self.source_terms.values())
        return terms

    def snapshot(self):
        """
        Return a state dictionary of the equation

        This only includes the equation sources as metadata

        Returns:
            A dictionary of the equation state
        """
        self.logger.debug('Snapshot of {!r}'.format(self))
        state = dict(
            sources=dict(metadata=self.source_coeffs),
            diffusion=dict(metadata=dict([self.diffusion_def])),
            transient=dict(metadata={self.varpath: self.term_transient.coeff}),
            )
        return state


class ModelClock(Variable):
    def __init__(self, model, **kwargs):
        self.model = model
        super(ModelClock, self).__init__(**kwargs)

    def _setValueProperty(self, newVal):
        super(ModelClock, self)._setValueProperty(newVal)
        self.model.on_time_updated()

    def _getValue(self):
        return super(ModelClock, self)._getValue()

    value = property(_getValue, _setValueProperty)

    def increment_time(self, dt):
        """
        Increment the clock

        Args:
            dt (float, PhysicalField): Time step in seconds
        """
        if dt <= 0:
            raise ValueError('Time increment must be positive!')

        dt = PhysicalField(dt, 's')
        self.value += dt

    def set_time(self, t):
        """
        Set the clock time in hours
        Args:
            t (float, PhysicalField): Time in hours

        """
        if t < 0:
            raise ValueError('Time must be positive!')

        t = PhysicalField(t, 'h')
        self.value = t

    @property
    def as_hms(self):
        """
        Return a tuple of (hour, minute, second)
        """
        h, m, s = self.inUnitsOf('h', 'min', 's')
        return h, m, s

    @property
    def as_hms_string(self):
        """
        Return a string of hour, min, sec
        """
        return '{}h {}m {:.0}s'.format(*self.as_hms)