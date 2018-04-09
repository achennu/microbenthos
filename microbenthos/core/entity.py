import importlib
import logging


# Todo: refactor :meth:`DomainEntity.set_domain` out of API

class Entity(object):
    """
    A base class to represent a model entity.

    It defines the interface for subclasses for:

        * Creation of instances through :meth:`from_params` and :meth:`from_dict`
        * Response to model clock through :meth:`on_time_updated`
        * (de-)serialization of state through :meth:`snapshot` and :meth:`restore_from`

    """

    def __init__(self, name = None, logger = None):

        if not logger:
            self.logger = logging.getLogger(__name__)
            self.logger.warning('No logger supplied, creating in base class: {}'.format(__name__))
        else:
            self.logger = logger

        #: The name of the entity
        self.name = name or 'unnamed'

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__name__,
            self.name)

    @classmethod
    def from_params(cls_, cls, init_params, post_params = None):
        """
        Create entity instance from the given parameters.

        The `cls` path is a string that specificies a class definition to be imported,
        and initialized with the given parameters. As a result, the returned instance need not be
        that of the calling class.

        Args:
            cls (str): The qualified `module.class_name`. If no `module` is in the string,
                then it is assumed to be "microbenthos".

            init_params (dict): Params to supply to the __init__ of the target class

            post_params (dict): Dictionary of params for :meth:`post_init` if available

        Returns:
            Instance of the entity

        Examples:

            >>> Entity.from_params(cls="Irradiance", ...)
            >>> Entity.from_params(cls="microbenthos.Process", ...)
            >>> Entity.from_params(cls="sympy.Lambda", ...)

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
            # logger.debug('Importing {}'.format(cls_modname))
            cls_module = importlib.import_module(cls_modname)
            CLS = getattr(cls_module, cls_name)
            logger.debug('Using class: {}'.format(CLS))
        except (ImportError, AttributeError):
            raise TypeError('Class {} in {} could not be found!'.format(cls_name, cls_modname))

        logger.debug('Init params: {}'.format(init_params))
        inst = CLS(**init_params)

        post_params = post_params or {}

        if hasattr(inst, 'post_init'):
            # logger.debug("Calling post_init for instance: {}".format(post_params))
            inst.post_init(**post_params)

        logger.debug('Created entity: {}'.format(inst))
        return inst

    @classmethod
    def from_dict(cls, cdict):
        """
        Pre-processor for :meth:`from_params` that extracts and sends the keys `"cls"`,
        `"init_params"` and `"post_params"`.

        Args:
            cdict (dict): parameters for :meth:`from_params`

        Returns:
            Instance of the entity created

        Raises:
            KeyError: If the `cls` key is missing in `cdict`
        """

        try:
            cls_path = cdict['cls']
        except KeyError:
            logger = logging.getLogger(__name__)
            logger.error('"cls" missing in def: {}'.format(cdict))
            raise KeyError('Config dict missing required key "cls"!')

        init_params = cdict.get('init_params', {})
        post_params = cdict.get('post_params', {})

        return cls.from_params(cls=cls_path, init_params=init_params, post_params=post_params)

    def post_init(self, **kwargs):
        """
        Hook to customize initialization of entity after construction by :meth:`.from_params`.

        This must be overriden by subclasses to be useful.

        Args:
            **kwargs: arbitrary parameters for :meth:`post_init`

        Returns:
            None

        """
        # self.logger.debug('Empty post_init on {}'.format(self))

    def on_time_updated(self, clocktime):
        """
        Hook to respond to the model clock changing.

        This must be overridden by subclasses to be useful.

        Args:
            clocktime (float, PhysicalField): The model clock time.
        """
        self.logger.debug('Updating {} for clock {}'.format(self, clocktime))

    def snapshot(self):
        """
        Returns a snapshot of the entity's state which will be a node in the nested structure to
        be consumed by :func:`~microbenthos.model.saver.save_snapshot`.

        Returns:
            dict: a representation of the state of the entity

        """
        raise NotImplementedError('Snapshot of entity {}'.format(self))

    __getstate__ = snapshot

    def restore_from(self, state, tidx):
        """
        Restore the entity from a saved state

        tidx is the time index. If it is `None`, then it is set to `slice(None, None)` and the
        entire time series is read out. Typically, `tidx = -1`, to read out the values of only
        the last time point.

        The `state` dictionary must be of the structure as defined in :meth:`.snapshot`.

        Raises:
            ValueError: if the state restore does not succeed
        """

        raise NotImplementedError('Restore of entity {}'.format(self))


class DomainEntity(Entity):
    """
    An :class:`Entity` that is aware of the model domain (see :mod:`~microbenthos.core.domain`),
    and serves as the base class for :class:`~microbenthos.core.MicrobialGroup`,
    :class:`~microbenthos.irradiance.Irradiance`, :class:`Variable`, etc.

    This class defines the interface to:

        * register the entity with the model domain (see :meth:`set_domain` and :attr:`domain`)
        * check that entity :meth:`has_domain`
        * respond to event :meth:`on_domain_set`
        * :meth:`setup` the entity for the simulation
    """

    def __init__(self, **kwargs):

        super(DomainEntity, self).__init__(**kwargs)
        self._domain = None

    @property
    def domain(self):
        """
        The domain for the entity

        Args:
             domain: An instance of :class:`SedimentDBLDomain` or similar

        Raises:
            RuntimeError: if domain is already set
        """
        return self._domain

    @domain.setter
    def domain(self, domain):
        if domain is None:
            return

        if self.domain:
            raise RuntimeError(
                '{} already has a domain. Cannot set again!'.format(self))

        self._domain = domain
        self.logger.debug('Added to domain: {}'.format(self))
        self.on_domain_set()

    def set_domain(self, domain):
        """
        Silly method that just does ``self.domain = domain``. Will likely be removed in a future
        version.
        """
        self.domain = domain
        self.logger.debug('{} domain set: {}'.format(self, domain))

    def check_domain(self):
        """
        A stricter version of :attr:`has_domain`

        Returns:
            ``True``: if :attr:`.domain` is not None

        Raises:
            RuntimeError: if :attr:`has_domain` is False

        """
        if not self.has_domain:
            raise RuntimeError('Domain required for setup of {}'.format(self))
        return True

    @property
    def has_domain(self):
        """
        Returns:
            ``True`` if :attr:`.domain` is not None
        """
        return self.domain is not None

    def on_domain_set(self):
        """
        Hook for when a domain is set

        To be used by sub-classes to setup sub-entities

        """

    def setup(self, **kwargs):
        """
        Method to set up the mat entity once a domain is available

        This may include logic to add any featuers it has also to the domain.

        To be overridden by subclasses
        """
        self.logger.debug('Setup empty: {}'.format(self))

    @property
    def is_setup(self):
        """
        A flag to indicate if an entity still needs setting up

        Must be overriden by subclasses to be useful
        """
        return True
