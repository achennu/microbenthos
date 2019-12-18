import itertools
import logging
import operator
from collections.abc import Mapping
from functools import reduce

import fipy.tools.numerix as np
import h5py as hdf
import sympy as sp
from fipy import PhysicalField, Variable
from sympy import Lambda, symbols

sp.init_printing()

from ..core import Entity, Expression, SedimentDBLDomain
from ..utils import snapshot_var, restore_var, CreateMixin
from .resume import check_compatibility, truncate_model_data
from .equation import ModelEquation


class MicroBenthosModel(CreateMixin):
    """
    The theater where all the actors of microbenthos come together in a
    concerted
    play driven by the clock. This is the class that encapsulates the nested
    structure and function of the various entities, variables, microbial
    groups and binds them
    with the domain.
    """
    schema_key = 'model'

    def __init__(self, **kwargs):
        """
        Initialize the model instance.

        Args:
            **kwargs:  definition dictionary assumed to be validated by
                :class:`~microbenthos.utils.loader.MicroBenthosSchemaValidator`.

        See Also:
            :meth:`.CreateMixin.create_from`

        """
        super(MicroBenthosModel, self).__init__()
        # the __init__ call is deliberately empty. will implement
        # cooeperative inheritance only
        # when necessary
        self.logger = logging.getLogger(__name__)
        self.logger.info('Initializing {}'.format(self.__class__.__name__))

        self._domain = None

        #: container (dict) of the
        # :class:`~microbenthos.core.microbes.MicrobialGroup` in the model
        self.microbes = {}
        #: container (dict) of the environmental variables and processes
        self.env = {}
        #: the full :mod:`fipy` equation of the model, coupling all
        # individual :attr:`.equations`
        self.full_eqn = None
        #: container (dict) of the various soure expressions of the
        # :attr:`.equations`
        self.source_exprs = {}
        #: container (dict) of the :class:`.ModelEquation` defined in the model
        self.equations = {}

        #: a :class:`fipy.Variable` subclass that serves as the
        # :class:`ModelClock`
        self.clock = ModelClock(self, value=0.0, unit='h', name='clock')

        self._setup(**kwargs)

    def add_formula(self, name, vars, expr):
        """
        Add a formula to the sympy namespace of :class:`Expression`

        Args:
            name (str): Name of the formula
            vars (str, list): Variables in the formula expression
            expr (str): The expression to be parsed by sympy

        Example:

            .. code-block:: python

                name = "optimum_response"
                variables = "x Ks Ki"
                expr = "x / (x + Ks) / (1 + x/Ki)"

        """
        self.logger.info('Adding formula {!r}: {}'.format(name, expr))
        try:
            func = Lambda(symbols(vars), expr)
            self.logger.debug('Formula {!r}: {}'.format(name, func))
            Expression._sympy_ns[name] = func
        except:
            self.logger.exception(
                'Invalid input for formula {}: vars={} expr={}'.format(name,
                                                                       vars,
                                                                       expr))
            raise ValueError('Invalid input for formula')

    @property
    def domain(self):
        """
        The model domain, typically :class:`.SedimentDBLDomain`
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
        Create a model entity from dictionary, and set it up with the model
        and domain.

        See Also: :meth:`.Entity.from_dict`

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
        Create an entity from its definition dictionary and store it into the
        target dictionary

        Args:
            target (str): Target dict such as ``"env"``, ``"microbes"``
            name (str): The key for the dictionary
            defdict (dict): Parameter definition of the entity

        """
        tdict = getattr(self, target)
        if name in tdict:
            self.logger.warning(
                "Entity {!r} exists in {}! Overwriting!".format(name, target))
        defdict['init_params']['name'] = name
        entity = self.create_entity_from(defdict)
        tdict[name] = entity
        self.logger.info('Added {} entity {} = {}'.format(target, name, entity))

    def _setup(self, **definition):
        """
        Set up the model instance from the `definition` dictionary, which is
        assumed to be validated by
        :class:`~microbenthos.utils.loader.MicroBenthosSchemaValidator`.
        """
        self.logger.debug(
            'Setting up model from definition: {}'.format(definition.keys()))

        domain_def = definition.get('domain')
        if domain_def:
            self.logger.info('Creating the domain')
            self.logger.debug(domain_def)
            if isinstance(domain_def, Mapping):
                self.domain = Entity.from_dict(domain_def)
            elif isinstance(domain_def, SedimentDBLDomain):
                self.domain = domain_def
            else:
                raise ValueError(
                    'Domain input {} of wrong type!'.format(type(domain_def)))

        # Load up the formula namespace
        if 'formulae' in definition:
            self.logger.info('Creating formulae')
            for name, fdict in definition['formulae'].items():
                self.add_formula(name, **fdict)

        env_def = definition.get('environment')
        if env_def:
            self.logger.info('Creating environment')

            for name, pdict in env_def.items():
                self._create_entity_into('env', name, pdict)

        microbes_def = definition.get('microbes')
        if microbes_def:
            self.logger.info('Creating microbes')

            for name, pdict in microbes_def.items():
                self._create_entity_into('microbes', name, pdict)

        if not self.all_entities_setup:
            self.entities_setup()

        eqndef = definition.get('equations')
        if eqndef:
            self.logger.info('Creating model equations')
            for eqnname, eqndef in eqndef.items():
                self.add_equation(eqnname, **eqndef)

        if self.equations:
            self.create_full_equation()

        self.logger.info('Model setup done')

    def entities_setup(self):
        """
        Check that the model entities are setup fully, if not attempt it for
        each entity in
        :attr:`.env` and :attr:.microbes`
        """
        for entity in itertools.chain(self.env.values(),
                                      self.microbes.values()):
            if not entity.is_setup:
                self.logger.info(
                    'Setting up dangling entity: {!r}'.format(entity))
                entity.setup(model=self)

    @property
    def all_entities_setup(self):
        """
        Flag that indicates if all entities have been setup
        """
        return all([e.is_setup for e in itertools.chain(
            self.env.values(),
            self.microbes.values())])

    def snapshot(self, base = False):
        """
        Create a snapshot of the model state.

        This method recursively calls the :meth:`snapshot` method of all
        contained entities,
        and compiles them into a nested dictionary. The dictionary has the
        structure of the
        model, as well as nodes with the numeric data and metadata. The state
        of the model can
        then be serialized, for example through :func:`.save_snapshot`,
        or processed through
        various exporters (in :mod:`~microbenthos.exporters`).

        Args:
            base (bool): Whether the entities should be converted to base units?

        Returns:
            dict: model state snapshot

        See Also:
            :func:`.save_snapshot` for details about the nested structure of
            the state and how it is
            processed.

        """
        self.logger.debug('Creating model snapshot')
        state = {}
        state['time'] = dict(data=snapshot_var(self.clock, base=base))
        if self.domain:
            domain = self.domain.snapshot(base=base)
        else:
            domain = {}
        state['domain'] = domain

        env = state['env'] = {}
        for name, obj in self.env.items():
            self.logger.debug('Snapshotting: {} --> {}'.format(name, obj))
            ostate = obj.snapshot(base=base)
            env[name] = ostate

        microbes = state['microbes'] = {}
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

    def restore_from(self, store, time_idx):
        """
        Restore the model entities from the given store

        Args:
            store (:class:`h5py:Group`): The root of the model data store
            time_idx (int): the index along the time series to restore. Uses
            python syntax,
            i.e first element is 0, second is 1, last element is -1, etc.

        Warning:
            This is a potentially destructive operation! After checking that we
            :meth:`.can_restore_from` the  given `store`,
            :func:`truncate_model_data` is called.
            This method modifies the data structure in the supplied store by
            truncating the
            datasets to the length of the time series as determined from
            `time_idx`. Only in the
            case of ``time_idx=-1`` it may not modify the  data.

        Raises:
            TypeError: if the store data is not compatible with model
            Exception: as raised by :func:`.truncate_model_data`.

        See Also:
            :func:`.check_compatibility` to see how the store is assessed to
            be compatible
            with the instantiated model.

            :func:`.truncate_model_data` for details on how the store is
            truncated.
        """
        self.logger.info('Restoring model from store: {}'.format(tuple(store)))

        if not self.can_restore_from(store):
            raise TypeError('Store incompatible to be restored from!')

        step_num = truncate_model_data(store, time_idx=time_idx)

        # now that the store has been truncated to the right length
        # read out and restore data from the last time point

        tidx = -1

        for name, envobj in self.env.items():
            self.logger.debug('Restoring {}: {}'.format(name, envobj))
            envobj.restore_from(store['env'][name], tidx)

        for name, microbe in self.microbes.items():
            microbe.restore_from(store['microbes'][name], tidx)

        for name, eqn in self.equations.items():
            eqn.restore_from(store['equations'][name], tidx)

        key = 'time'
        self.clock.setValue(restore_var(store[key], tidx))
        self.logger.info('Restored model clock to {}'.format(self.clock))

    def can_restore_from(self, store):
        """
        Check if the model can be resumed from the given store

        Args:
            store (:class:`hdf.Group`): The root of the model data store

        Returns:
            True if it is compatible

        """
        self.logger.info('Checking if model can resume from {}'.format(store))
        try:
            check_compatibility(self.snapshot(), store)
            return True
        except:
            self.logger.warning('Model & stored data not compatible',
                                exc_info=True)
            return False

    def add_equation(self, name, transient, sources = None, diffusion = None,
                     track_budget = False):
        """
        Create a transient reaction-diffusion equation for the model.

        The term definitions are provided as `(model_path, coeff)` pairs to
        be created for the
        transient term, diffusion term and source terms.

        If all inputs are correct, it creates and finalizes a
        :class:`.ModelEquation` instance,
        stored in :attr:`.equations`.

        Args:
            name (str): Identifier for the equation
            transient (tuple): Single definition for transient term
            sources (list): A list of definitions for source terms
            diffusion (tuple): Single definition for diffusion term
            track_budget (bool): flag whether the variable budget should be
            tracked over time

        """
        self.logger.debug(
            'Creating equation for transient={}, diffusion={} and '
            'sources={}'.format(
                transient,
                diffusion,
                sources))

        if name in self.equations:
            raise RuntimeError(
                'Equation with name {!r} already exists!'.format(name))

        def is_pair_tuple(obj):
            try:
                assert isinstance(obj, (tuple, list))
                _, __ = obj
                return True
            except:
                return False

        if not is_pair_tuple(transient):
            raise ValueError('Transient term must be a (path, coeff) tuple!')

        if not diffusion and not sources:
            raise ValueError(
                'One or both of diffusion and source terms must be given.')

        if diffusion:
            if not is_pair_tuple(diffusion):
                raise ValueError('Diffusion term must be a (path, coeff) tuple')

        if sources:
            improper = list(filter(lambda x: not is_pair_tuple(x), sources))
            if improper:
                self.logger.error(f'Equation sources improper: {sources}')
                raise ValueError(
                    'Source terms not (path, coeff) tuples: {}'.format(
                        improper))

        eqn = ModelEquation(self, *transient, track_budget=track_budget)

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
        Create the full equation (:attr:`.full_eqn`) of the model by coupling
        the
        individual :attr:`.equations`.
        """
        if not self.equations:
            raise RuntimeError('No equations available for model!')

        self.logger.info(
            'Creating full equation from {}'.format(self.equations.keys()))

        full_eqn = reduce(operator.and_,
                          [eqn.obj for eqn in self.equations.values()])
        self.logger.info('Full model equation: {!r}'.format(full_eqn))

        self.full_eqn = full_eqn

        # self.logger.debug('Collecting unique source term expressions')
        # for eqn in self.equations.values():
        #
        #     for name, expr in eqn.source_exprs.items():
        #
        #         if name not in self.source_exprs:
        #             self.source_exprs[name] = expr
        #
        #         else:
        #             old = self.source_exprs[name]
        #             if old is not expr:
        #                 raise RuntimeError(
        #                     'Another source with same name {!r} exists from
        #                     different '
        #                     'equation!'.format(
        #                         name))

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
            raise TypeError(
                'Path should dotted string, but got {!r}'.format(path))

        S = self
        for p in parts:
            self.logger.debug('Getting {!r} from {}'.format(p, S))
            S_ = getattr(S, p, None)
            if S_ is None:
                try:
                    S = S[p]
                except (KeyError, TypeError):
                    raise ValueError(
                        'Unknown model path {!r}'.format(
                            '.'.join(parts[:parts.index(p) + 1])))
            else:
                S = S_

        obj = S
        self.logger.debug('Got obj: {!r}'.format(obj))
        return obj

    def on_time_updated(self):
        """
        Callback function to update the time on all the stored entities
        """
        clock = self.clock()
        self.logger.info('Updating entities for model clock: {}'.format(clock))

        for name, obj in self.env.items():
            obj.on_time_updated(clock)

        for name, obj in self.microbes.items():
            obj.on_time_updated(clock)

    def revert_vars(self):
        """
        Revert vars to the old settings. This is used when sweeping equations has to be rolled back
        """
        for var in self.full_eqn._vars:
            self.logger.info('Setting {!r} to old value'.format(var))
            var.value = var.old.copy()

    def update_vars(self):
        """
        Update all stored variables which have an `hasOld` setting. This is
        used while sweeping
        for solutions.
        """

        self.logger.debug(
            'Updating model variables. Current time: {}'.format(self.clock))
        updated = []
        for name, obj in self.env.items():
            path = 'env.{}'.format(name)
            if hasattr(obj, 'var'):
                try:
                    obj.var.updateOld()
                    self.logger.debug("Updated old: {}".format(path))

                    if obj.clip_min is not None or obj.clip_max is not None:
                        obj.var.value = np.clip(obj.var.value, obj.clip_min,
                                                obj.clip_max)
                        self.logger.info('Clipped {} between {} and {}'.format(
                            obj, obj.clip_min, obj.clip_max
                            ))
                    updated.append(path)
                except AssertionError:
                    self.logger.debug(
                        '{} = {!r}.var.updateOld failed'.format(path, obj))

            else:
                self.logger.debug('env.{!r} not model variable'.format(obj))

        for name, microbe in self.microbes.items():
            for fname, feat in microbe.features.items():
                path = 'microbes.{}.features.{}'.format(name, fname)
                if hasattr(feat, 'var'):
                    try:
                        feat.var.updateOld()
                        self.logger.debug("Updated old: {}".format(path))
                        updated.append(path)
                    except AssertionError:
                        self.logger.debug(
                            '{} = {!r}.var.updateOld failed'.format(path, obj))
                else:
                    self.logger.debug(
                        '{}={!r} is not model variable'.format(path, obj))

        return updated

    def update_equations(self, dt):
        """
        Update the :attr:`.equations` for the time increment.

        Args:
            dt (PhysicalField): the time step duration
        """
        self.logger.debug(
            'Updating model equations. Current time: {} dt={}'.format(
                self.clock, dt))

        for eqn in self.equations.values():
            eqn.update_tracked_budget(dt)


class ModelClock(Variable):
    """
    Subclass of :class:`fipy.Variable` to implement hooks and serve as clock
    of the model.
    """

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
