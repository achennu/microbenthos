import logging

from fipy import PhysicalField
from fipy.tools import numerix

from .entity import DomainEntity
from ..utils.snapshotters import snapshot_var, restore_var


class ModelVariable(DomainEntity):
    """
    A class to represent a variable on the model domain.

    This class serves as means for defining features such as environmental variables, chemical
    analytes or microbiological features (biomass). The class allows defining the variable but
    deferring the initialization of the associated :class:`CellVariable` until the domain is
    available.

    The interface defined allows to:

        * set boundary condition to :meth:`.constrain` the values
        * :meth:`.seed` the variable values
        * create a :meth:`.snapshot` of the state and :meth:`restore_from` it
        * set :attr:`.clip_min` and :attr:`.clip_max` limits on the values

    """

    def __init__(self, create,
                 constraints = None,
                 seed = None,
                 clip_min = None,
                 clip_max = None,
                 **kwargs):
        """
        Configure the creation of a variable and its boundary conditions

        Args:
            name (str): The name of the variable

            create (dict): parameters for variable creation (see :meth:`.create`)

            constraints (dict): Mapping of `location` to value of boundary condition
                through :meth:`.constrain`

            seed (dict): parameters to seed initial value of variable

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        kwargs['logger'] = self.logger
        super(ModelVariable, self).__init__(**kwargs)

        self.logger.debug('Init in {} {!r}'.format(self.__class__.__name__, self.name))

        self.var = None
        """:type : :class:`fipy.CellVariable` 

        Object created on domain.mesh"""

        self.create_params = self.check_create(**create)
        """:type : dict

        Validated dict of params for creation of variable"""

        self.logger.debug('{} saving create params {}'.format(self, self.create_params))

        #: mapping of domain location to values for boundary conditions (see :meth:`constrain`)
        self.constraints = constraints or dict()
        self.check_constraints(self.constraints)

        self.seed_params = seed or dict()

        #: the min value to which the variable array is clipped
        self.clip_min = clip_min
        #: the max value to which the variable array is clipped
        self.clip_max = clip_max

    def __repr__(self):
        return 'Var({})'.format(self.name)

    @staticmethod
    def check_create(**params):
        """
        Check that the given `params` are valid for creating the variable once the domain is
        available

        Args:
            name (str): a required identifier string

            unit (str): a string like ("kg/m**3") that defines the physical units of the variable

            value (float, :class:`~numpy.ndarray`, :class:`~fipy.PhysicalField`): the value to set
                for the variable. If a :class:`PhysicalField` is supplied, then its (base) unit is
                used as `unit` and overrides any supplied `unit`.

        Returns:
            dict: the params dictionary to be used

        Raises:
            ValueError: if no `name` is supplied

            ValueError: if `unit` is not a valid input for :class:`PhysicalField`


        Note:
            Due to limitation in :mod:`fipy` (v3.1.3) that meshes do not accept arrays
            :class:`PhysicalField` as inputs, the variables defined here are cast into base units
            since the domain mesh is created in meters.

        """

        name = params.get('name')
        if name:
            raise ValueError('Create params should not contain name. Will be set from init name.')

        from fipy import PhysicalField
        value = params.get('value', 0.0)
        if hasattr(value, 'unit'):
            unit = value.unit
        else:
            unit = params.get('unit')

        try:
            p = PhysicalField(value, unit)
        except:
            raise ValueError('{!r} is not a valid unit!'.format(unit))

        pbase = p.inBaseUnits()
        params['unit'] = pbase.unit.name()
        params['value'] = pbase.value

        return params

    @staticmethod
    def check_constraints(constraints):
        """
        Check that constraints is a mapping of location to value of boundary conditions.
        Recognized location values are: `"top", "bottom"`.

        Raises:
            TypeError if `constraints` is not a mapping
            ValueError if `loc` is not valid
            ValueError if `value` is not single-valued

        """
        logger = logging.getLogger(__name__)

        locs = ('top', 'bottom', 'dbl', 'sediment')
        try:
            for loc, val in dict(constraints).items():
                pass
        except (ValueError, TypeError):
            logger.error('Constraints not a mapping of pairs: {}'.format(constraints))
            raise ValueError('Constraints should be mapping of (location, value) pairs!')

        for loc, val in dict(constraints).items():
            if loc not in locs:
                raise ValueError('Constraint loc={!r} unknown. Should be in {}'.format(
                    loc, locs
                    ))
            try:
                if isinstance(val, PhysicalField):
                    v = float(val.value)
                else:
                    v = float(val)
            except:
                raise ValueError('Constraint should be single-valued, not {!r}'.format(val))

    def setup(self, **kwargs):
        """
        Once a domain is available, :meth:`.create` the variable with the requested parameters and
        apply any constraints.

        Constraints are specified as:

            * ``"top"`` : ``domain.mesh.facesLeft``
            * ``"bottom"`` : ``domain.mesh.facesRight``
            * ``"dbl"`` : ``slice(0, domain.idx_surface)``
            * ``"sediment:`` : ``slice(domain.idx_surface, None)``

        Note:
            The constraints "dbl" and "sediment" are not yet tested to work with fipy
            equations. It is likely that this formulation may not work correctly.

            Specifying both "top" and "dbl" or "bottom" and "sediment" does not currently raise
            an error, but instead warning messages are logged.

        """

        self.check_domain()

        self.create(**self.create_params)

        if self.seed_params:
            self.seed(profile=self.seed_params['profile'], **self.seed_params.get('params', {}))
            if self.create_params.get('hasOld'):
                self.var.updateOld()

        self._LOCs = {
            'top': self.domain.mesh.facesLeft,
            'bottom': self.domain.mesh.facesRight,
            'dbl': slice(0, self.domain.idx_surface),
            'sediment': slice(self.domain.idx_surface, None)
            }

        invalid_pairs = [('top', 'dbl'), ('bottom', 'sediment')]
        for pair in invalid_pairs:
            if all(p in self.constraints for p in pair):
                self.logger.warning('Constraints specified with invalid pair: {}'.format(pair))

        for loc, value in dict(self.constraints).items():
            self.constrain(loc, value)

    def create(self, value, unit = None, hasOld = False, **kwargs):
        """
        Create a :class:`~fipy.CellVariable` by calling :meth:`.domain.create_var`.

        Args:
            value (int, float, array, PhysicalField): the value for the array

            unit (str): physical units string for the variable. Is overridden if `value` is a
                `PhysicalField`.

            hasOld (bool): flag to indicate that the variable should store the older value
                separately (see :class:`fipy.CellVariable`).

        Returns:
            instance of the variable created

        Raises:
            RuntimeError: if a domain variable with `name` already exists, or no mesh exists on
                the domain.

            ValueError: if value.shape is not 1 or the domain shape

        """
        self.logger.debug('Creating variable {!r} with unit {}'.format(self.name, unit))

        self.var = self.domain.create_var(name=self.name, value=value,
                                          unit=unit, hasOld=hasOld,
                                          **kwargs)

        return self.var

    def constrain(self, loc, value):
        """
        Constrain the variable at the given location to the given value

        Args:
            loc (str): One of ``("top", "bottom", "dbl", "sediment")``

            value (float, :class:`PhysicalField`): a numeric value for the constraint

        Returns:
            None

        Raises:
            TypeError: if the units for `value` are incompatible with :attr:`.var` units

            ValueError: for improper values for `loc`

            ValueError: if value is not a 0-dimension array

            RuntimeError: if variable doesn't exist

        """
        if self.var is None:
            raise RuntimeError('Variable {} does not exist!'.format(self.name))

        self.logger.debug("Setting constraint for {!r}: {} = {}".format(self.var, loc, value))

        if loc in ('top', 'bottom'):
            mask = self._LOCs[loc]

        else:
            mask = numerix.zeros(self.var.shape, dtype=bool)

            try:
                L = self._LOCs[loc]
                self.logger.debug('Constraint mask loc: {}'.format(L))
                mask[L] = 1
            except KeyError:
                raise ValueError('loc={} not in {}'.format(loc, tuple(self._LOCs.keys())))

        if isinstance(value, PhysicalField):
            value = value.inUnitsOf(self.var.unit)
        else:
            value = PhysicalField(value, self.var.unit)

        self.logger.info('Constraining {!r} at {} = {}'.format(self.var, loc, value))

        self.var.constrain(value, mask)

    def seed(self, profile, **kwargs):
        """
        Seed the value of the variable based on the profile and parameters

        Available profiles are:

            * "normal"
                * normal distribution of values from :data:`scipy.stats.norm`
                * `loc` and `scale` in units compatible with domain mesh
                * `coeff` to multiply the distribution with, in units compatible with that of
                  :attr:`.var`
                * the normal distribution is created to have unit height for different `loc` and
                  `scale` values

            * "linear"
                * uses :func:`~numpy.linspace` to fill the first dimension of :attr:`.var`
                * `start`: the start value given, else taken from constraint "top"
                * `stop`: the stop value given, else taken from constraint "bottom"

            * "lognormal"
                * lognormal distributuion from :data:`scipy.stats.lognorm`
                * `loc` and `scale` should be in units compatible with domain mesh
                * `shape` for lognorm is hard-coded to 1.25

        Args:
            profile (str): The type of profile to use
            **kwargs: Parmeters for the profile

        Returns:
            None

        Raises:
            ValueError: if incompatible units encountered


        """
        PROFILES = ('linear', 'normal', 'lognormal')

        if profile not in PROFILES:
            raise ValueError('Unknown profile {!r} not in {}'.format(profile, PROFILES))

        if profile == 'normal':
            from scipy.stats import norm
            loc = kwargs['loc']
            scale = kwargs['scale']
            coeff = kwargs['coeff']

            C = 1.0 / numerix.sqrt(2 * numerix.pi)

            # loc and scale should be in units of the domain mesh
            if hasattr(loc, 'unit'):
                loc_ = loc.inUnitsOf(self.domain.depths.unit).value
            else:
                loc_ = loc

            if hasattr(scale, 'unit'):
                scale_ = scale.inUnitsOf(self.domain.depths.unit).value
            else:
                scale_ = scale

            if hasattr(coeff, 'unit'):
                # check if compatible with variable unit
                try:
                    c = coeff.inUnitsOf(self.var.unit)
                except TypeError:
                    self.logger.error(
                        'Coeff {!r} not compatible with variable unit {!r}'.format(coeff,
                                                                                   self.var.unit.name()))
                    raise ValueError('Incompatible unit of coefficient')

            self.logger.info(
                'Seeding with profile normal loc: {} scale: {} coeff: {}'.format(loc_, scale_,
                                                                                 coeff))

            normrv = norm(loc=loc_, scale=C ** 2 * scale_)
            val = coeff * normrv.pdf(self.domain.depths) * C * scale_

            self.var.value = val

        elif profile == 'lognormal':
            from scipy.stats import lognorm

            loc = kwargs['loc']
            scale = kwargs['scale']
            coeff = kwargs['coeff']
            lognorm_shape = 1.25
            lognorm_mult = 1.74673269133
            # this depends on the shape, so we hardcode it here
            C = numerix.sqrt(2 * numerix.pi)

            # loc and scale should be in units of the domain mesh
            if hasattr(loc, 'unit'):
                loc_ = loc.inUnitsOf(self.domain.depths.unit).value
            else:
                loc_ = loc

            if hasattr(scale, 'unit'):
                scale_ = scale.inUnitsOf(self.domain.depths.unit).value
            else:
                scale_ = scale

            if hasattr(coeff, 'unit'):
                # check if compatible with variable unit
                try:
                    c = coeff.inUnitsOf(self.var.unit)
                except TypeError:
                    self.logger.error(
                        'Coeff {!r} not compatible with variable unit {!r}'.format(
                            coeff, self.var.unit.name()))
                    raise ValueError('Incompatible unit of coefficient')

            self.logger.info(
                'Seeding with profile lognormal loc: {} scale: {} coeff: {}'.format(
                    loc_, scale_, coeff))

            rv = lognorm(lognorm_shape, loc=loc_, scale=C ** 2 * scale_ / lognorm_shape)
            val = coeff * rv.pdf(self.domain.depths) * C * scale_

            self.var.value = val

        elif profile == 'linear':
            start = kwargs.get('start')
            stop = kwargs.get('stop')

            if start is None:
                start = self.constraints.get('top')
                if start is None:
                    raise ValueError('Seed linear has no "start" or "top" constraint')
                else:
                    start = PhysicalField(start, self.var.unit)
                    self.logger.info('Linear seed using start as top value: {'
                                  '}'.format(start))

            if stop is None:
                stop = self.constraints.get('bottom')
                if stop is None:
                    raise ValueError('Seed linear has no "stop" or "bottom" constraint')
                else:
                    stop = PhysicalField(stop, self.var.unit)
                    self.logger.info('Linear seed using stop as bottom value: {'
                                  '}'.format(stop))

            N = self.var.shape[0]

            if hasattr(start, 'unit'):
                start_ = start.inUnitsOf(self.var.unit).value
            else:
                start_ = start

            if hasattr(stop, 'unit'):
                stop_ = stop.inUnitsOf(self.var.unit).value
            else:
                stop_ = stop

            self.logger.info(
                'Seeding with profile linear: start: {} stop: {}'.format(start_, stop_))

            val = numerix.linspace(start_, stop_, N)
            self.var.value = val

        self.logger.debug('Seeded {!r} with {} profile'.format(self, profile))

    def snapshot(self, base = False):
        """
        Returns a snapshot of the variable's state, with the following structure:

            * data:
                * (:attr:`.var`, `dict(unit=:meth:`.var.unit.name()`)

            * metadata
                * constraint_<name>: constraint_value (in :attr:`.constraints`)

        Args:
            base (bool): Convert to base units?

        Returns:
            dict: the variable state

        """
        self.logger.debug('Snapshot: {}'.format(self))

        self.check_domain()

        state = dict()

        state['data'] = snapshot_var(self.var, base=base)

        meta = state['metadata'] = {}
        for cloc, cval in self.constraints.items():
            key = 'constraint_{}'.format(cloc)
            meta[key] = str(cval)

        return state

    def restore_from(self, state, tidx):
        """
        Restore the variable from a saved state

        It sets the value of the :attr:`.var` to that stored in the `state`.

        Args:
            state (dict): the saved state
            tidx (int, None): passed to :func:`.restore_var`

        The `state` dictionary must be of the structure:
            * `data`: (array, dict(unit=str))

        Raises:
            ValueError: if the state restore does not succeed
        """
        self.logger.debug('Restoring {} from state: {}'.format(self, tuple(state)))

        self.check_domain()

        try:
            self.var.setValue(restore_var(state, tidx))
            self.logger.debug('{} restored state'.format(self))
        except:
            self.logger.exception('Data restore failed')
            raise ValueError('{}: restore of "data" failed!'.format(self))
