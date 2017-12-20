import importlib
import inspect
import logging

from fipy import PhysicalField
from fipy.tools import numerix

from microbenthos.domain import SedimentDBLDomain


class Entity(object):
    def __init__(self, logger = None):

        if not logger:
            self.logger = logging.getLogger(__name__)
            self.logger.warning('No logger supplied, creating in base class: {}'.format(__name__))
        else:
            self.logger = logger

    @classmethod
    def from_params(cls_, cls, init_params, post_params = None):
        """
        Create entity instance from supplied CLS path and init parameters

        CLS is a string such as `Irradiance` or `microbenthos.Process` or `sympy.Lambda`

        Args:
            cls (str): The qualified `module.class_name`. If no `module` is in the string,
            then it is assummed to be `"microbenthos"`

            init_params (dict): Dictionary of params to supply to the class __init__

            post_params (dict): Dictionary of params for :meth:`post_init` if available

        Returns:
            Instance of the entity

        """
        logger = logging.getLogger(__name__)
        logger.debug('Setting up entity from cls: {}'.format(cls))
        try:
            cls_modname, cls_name = cls.rsplit('.', 1)
        except ValueError:
            # raise ValueError('Path {} could not be split into module & class'.format(cls))
            # this is then just a class name to import from microbenthos
            cls_modname = 'microbenthos'
            cls_name = cls

        try:
            logger.debug('Importing {}'.format(cls_modname))
            cls_module = importlib.import_module(cls_modname)
            CLS = getattr(cls_module, cls_name)
            logger.debug('Using class: {}'.format(CLS))
        except (ImportError, AttributeError):
            raise TypeError('Class {} in {} could not be found!'.format(cls_name, cls_modname))

        logger.debug('Init params: {}'.format(init_params))
        inst = CLS(**init_params)

        post_params = post_params or {}

        if hasattr(inst, 'post_init'):
            logger.debug("Calling post_init for instance: {}".format(post_params))
            inst.post_init(**post_params)

        logger.info('Created entity: {}'.format(inst))
        return inst

    @classmethod
    def from_dict(cls, cdict):
        """
        Create the entity instance from a supplied dictionary of parameters.

        Args:
            cdict: This dictionary must contain a key `cls` which contains the import path to the
            class (example: `"microbenthos.irradiance.Irradiance"`, and a key `init_params` whose
            value
            will be passed to the constructor of the class. The rest of the dictionary (except
            `cls`) will be
            passed to :meth:`.post_init` to allow subclasses to finish setup.

        Returns:
            New instance of the entity

        Raises:
              KeyError: If the `cls` key is missing
              ValueError: If the cls is not a valid module path
              TypeError: If the class cannot be imported
        """
        try:
            cls_path = cdict.pop('cls')
        except KeyError:
            raise KeyError('Config dict missing required key "cls"!')

        init_params = cdict.get('init_params', {})
        post_params = cdict.get('post_params', {})

        return cls.from_params(cls=cls_path, init_params=init_params, post_params=post_params)

    def post_init(self, **kwargs):
        """
        Hook to customize initialization of entity after construction by :meth:`.from_dict`. This
        must be overriden by subclasses, to be useful.

        Args:
            **kwargs:

        Returns:
            None
        """
        self.logger.debug('Empty post_init on {}'.format(self))

    def update_time(self, clocktime):
        """
        Method which should update the entity features for the simulation clocktime

        :param float clocktime: The simulation time (units depends on the solver setup)
        """
        self.logger.debug('Updating {} for clocktime {}'.format(self, clocktime))


class DomainEntity(Entity):
    """
    A base class that represents entities in the microbenthic environment. This can be used to
    subclass microbial groups, chemical reactions, or other parameters. The class provides a
    uniform interface to add the entity to the simulation domain and setup parameters and update
    according to the simulation clock.
    """

    def __init__(self, domain_cls = SedimentDBLDomain, **kwargs):

        super(DomainEntity, self).__init__(**kwargs)

        assert inspect.isclass(domain_cls), 'domain_cls should be a class! Got {}'.format(
            type(domain_cls)
            )
        self.domain_cls = domain_cls

        self._domain = None

    @property
    def domain(self):
        """
        Set the domain for the entity

        Args:
             domain: An instance of :class:`SedimentDBLDomain`

        Raises:
            RuntimeError: if domain is already set
            TypeError: if domain is of wrong type

        """
        return self._domain

    @domain.setter
    def domain(self, domain):
        if domain is None:
            return

        if self.domain:
            raise RuntimeError(
                '{} already has a domain. Cannot set again!'.format(self))

        if not isinstance(domain, self.domain_cls):
            self.logger.warning('Domain must be an instance of {}, not {}'.format(
                self.domain_cls.__name__, type(domain)))
        # raise TypeError('Wrong domain type received!')

        self._domain = domain
        self.logger.info('Added to domain: {}'.format(self))
        self.on_domain_set()

    def set_domain(self, domain):
        self.domain = domain

    def check_domain(self):
        if self.domain is None:
            raise RuntimeError('Domain required for setup')
        return self.has_domain

    @property
    def has_domain(self):
        return isinstance(self.domain, self.domain_cls)

    def on_domain_set(self):
        """
        Hook for when a domain is set

        To be used by sub-classes to setup sub-entities

        """

    def setup(self):
        """
        Method to set up the mat entity once a domain is available

        This may include logic to add any featuers it has also to the domain.

        To be overridden by subclasses
        """
        self.logger.debug('Setup: {}'.format(self))
        raise NotImplementedError('Setup of {}'.format(self.__class__.__name__))


class Variable(DomainEntity):
    """
    A helper class to represent a variable for the model domain, which can create the variable,
    apply boundary conditions.
    """

    def __init__(self, name, create,
                 constraints = None,
                 **kwargs):
        """
        Configure the creation of a variable and its boundary conditions

        Args:
            name (str): The name of the variable
            create (dict): parameters for variable creation (see :meth:`.create`)
            constraints (dict): Mapping of `location` to value of boundary condition
            through :meth:`.constrain`.
            **kwargs:
        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        kwargs['logger'] = self.logger
        super(Variable, self).__init__(**kwargs)

        self.logger.debug('Init in DomainVariable for {!r}'.format(name))
        self.name = name
        self.var = None

        self.create_params = create

        self.check_create(**self.create_params)

        self.constraints = constraints or dict()
        self.check_constraints(self.constraints)

    def __repr__(self):
        return 'Var({})'.format(self.name)

    @staticmethod
    def check_create(**params):

        from fipy import PhysicalField
        unit = params.get('unit')
        if unit:
            try:
                p = PhysicalField(1, params['unit'])
            except:
                raise ValueError('{!r} is not a valid unit!'.format(params['unit']))

        vtype = params.get('vtype')
        if vtype:
            if vtype not in ('cell', 'basic'):
                raise ValueError('Variable type not known {!r} in ("cell", "basic")'.format(vtype))

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

    def setup(self):
        """
        Once a domain is available, create the variable with the requested parameters and apply
        any constraints.

        Returns:
            Instance of the variable created

        """

        self.check_domain()

        self.create(**self.create_params)

        for loc, value in dict(self.constraints).items():
            self.constrain(loc, value)

    def create(self, value, unit = None, hasOld = False, vtype = 'cell'):
        """
        Create a :class:`~fipy.Variable` on the domain.


        A `vtype` of `"cell"` is intended to creates variables with one dimension equal to
        the domain size. So if the input to this is:
            * a single number, then the number is broadcast to an array the shape of the domain.
            * a :class:`~fipy.PhysicalField` of a single value or of an array the size of the
            domain, then a variable of the domain size is created. The unit of the
            `PhysicalField` is used, and any supplied `unit` keyword is ignored.
            * a :class:`~fipy.PhysicalField` of shape not matching the domain size,
            then a variable would be created that is not representable on the domain. Currently,
            this raises a `ValueError`.

        A `vtype` of `"basic"` is intended to create variables that can be used as dependencies,
        and are not bound to the domain. So, the shape of the variable is the same as the input
        `value`. Again, `unit` is overriden if `value` is a `PhysicalField`.

        Args:
            value (int, float, array, PhysicalField): the value for the array
            unit (str): physical units string for the variable. Is overriden if `value` is a
            `PhysicalField`.
            hasOld (bool): Whether the variable of `vtype = "cell"` keeps the old values,
            and must be manually updated. (default: False). This setting is ignored for `"basic"`
            variables.
            vtype: string indicating type to create. Either "cell" or "basic". (default: "cell")

        Returns:
            instance of the variable created

        Raises:
            RuntimeError: if a domain variable with `name` already exists, or no mesh exists on
            the domain.
            ValueError: for `"cell"` variables, if value.shape is not 1 or the domain shape

        """
        self.logger.debug('Creating {} variable {!r} with unit {}'.format(vtype, self.name, unit))
        kwargs = dict(unit=unit)

        from fipy.tools import numerix, PhysicalField
        if vtype == "cell":
            varr = numerix.atleast_1d(value)
            if varr.ndim != 1:
                raise ValueError(
                    'Cell variable dimensions must be 0 or 1, not {}'.format(varr.ndim))

            if varr.shape[0] not in (1, self.domain.domain_Ncells):
                raise ValueError(
                    'Cell variable of shape {} cannot be broadcast to domain of shape {}'.format(
                        varr.shape, self.domain.domain_Ncells))

            kwargs['hasOld'] = bool(hasOld)

        if unit and isinstance(value, PhysicalField):
            vunit = str(value.unit.name())
            if vunit != "1":
                # value has units
                self.logger.warning('Value for {!r} has units {!r}, which will override '
                                    'supplied {}'.format(self.name, vunit, unit))

        if isinstance(value, int):
            value = float(value)
            # integer type can have comparison issue with physical units

        kwargs['value'] = value

        self.var = self.domain.create_var(vname=self.name,
                                          vtype=vtype,
                                          **kwargs)
        return self.var

    def constrain(self, loc, value):
        """
        Constrain the variable at the given location to the given value

        Args:
            loc (str): One of `("top", "bottom", "dbl", "sediment")
            value (numeric): a numeric value for the constraint, such as a number of a
            `PhysicalField`

        Returns:
            None

        Raises:
            ValueError for improper values for `loc`
            ValueError if value is not a 0-dimension array
            RuntimeError if variable doesn't exist

        """

        if self.var is None:
            raise RuntimeError('Variable {} does not exist!'.format(self.name))

        mask = numerix.zeros_like(self.var, dtype=bool)

        LOC = {
            'top': 0,
            'bottom': -1,
            'dbl': slice(0, self.domain.idx_surface),
            'sediment': slice(self.domain.idx_surface, -1)
            }
        try:
            L = LOC[loc]
            mask[L] = 1
        except KeyError:
            raise ValueError('loc={} not in {}'.format(loc, tuple(LOC.keys())))

        if isinstance(value, PhysicalField):
            value = value.inUnitsOf(self.var.unit)
        else:
            value = PhysicalField(value, self.var.unit)

        self.logger.info('Constraining {!r} at {} = {}'.format(self.var, loc, value))
        self.var.constrain(value, mask)
