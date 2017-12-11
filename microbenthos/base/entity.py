import logging
logger = logging.getLogger(__name__)

import inspect
from microbenthos.domain import SedimentDBLDomain


class Entity(object):
    """
    A base class that represents entities in the microbenthic environment. This can be used to
    subclass microbial groups, chemical reactions, or other parameters. The class provides a
    uniform interface to add the entity to the simulation domain and setup parameters and update
    according to the simulation clock.
    """

    def __init__(self, domain_cls=SedimentDBLDomain):

        assert inspect.isclass(domain_cls), 'domain_cls should be a class! Got {}'.format(
            type(domain_cls)
            )
        self.domain_cls = domain_cls

        self._domain = None
        self.features = {}

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
                '{} already in domain {}. Cannot set again!'.format(self, self.domain))

        if not isinstance(domain, self.domain_cls):
            raise TypeError('Domain must be an instance of {}, not {}'.format(
                self.domain_cls.__name__, type(domain)))

        self._domain = domain
        logger.info('Added to domain: {}'.format(self))
        assert isinstance(self.domain, self.domain_cls)

    def set_domain(self, domain):
        self.domain = domain

    def check_domain(self):
        if self.domain is None:
            raise RuntimeError('Domain required for setup')
        return self.has_domain

    @property
    def has_domain(self):
        return isinstance(self.domain, self.domain_cls)

    def setup(self):
        """
        Method to set up the mat entity once a domain is available

        This may include logic to add any featuers it has also to the domain.

        To be overridden by subclasses
        """
        logger.debug('Setup: {}'.format(self))
        raise NotImplementedError('Setup of {}'.format(self.__class__.__name__))

    def update_time(self, clocktime):
        """
        Method which should update the entity features for the simulation clocktime

        :param float clocktime: The simulation time (units depends on the solver setup)
        """
        logger.debug('Updating {} for clocktime {}'.format(self, clocktime))
