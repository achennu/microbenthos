"""
Base class definition for exporters
"""

import abc
import logging


class BaseExporter(object, metaclass=abc.ABCMeta):
    """
    An abstract base class to define the interface for model state exporters to be used by the
    classes defined in :mod:`~microbenthos.runners`.
    """
    _exports_ = ''
    __version__ = ''
    is_eager = False

    def __init__(self, name = 'exp', logger = None, **kwargs):

        if not logger:
            self.logger = logging.getLogger(__name__)
            self.logger.warning('No logger supplied, creating in base class: {}'.format(__name__))
        else:
            self.logger = logger

        self.name = name

        if not self._exports_:
            raise ValueError('{} "_exports_" should not be empty'.format(
                self.__class__.__name__
                ))

        if not self.__version__:
            raise ValueError('{} "__version__" should not be empty'.format(
                self.__class__.__name__
                ))

        #: flag indicating if export has started
        self.started = False

        #: the runner instance operating this exporter
        self.runner = None

        self.logger.info('{} info: {}'.format(self, self.get_info()))

        self.logger.debug('ignoring kwargs: {}'.format(kwargs))

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.name)

    def setup(self, runner, state):
        """
        Set up the exporter

        Args:
            runner (object): instance of the runner class operating it
            state (dict): a model state snapshot

        Returns:

        """
        self.logger.debug('Setting up {}'.format(self))
        self.runner = runner
        self.prepare(state)
        self.started = True

    @property
    def sim(self):
        """
        The simulation object of the runner, if any

        Returns:
            None or :class:`~microbenthos.Simulation`

        """
        try:
            return self.runner.simulation
        except AttributeError:
            return None

    @abc.abstractmethod
    def prepare(self, state):
        """
        Prepare the exporter based on the model state

        Args:
            state (dict): a model snapshot dict

        """
        raise NotImplementedError('Should be implemented in subclass')

    def close(self):
        """
        Close the exporter by calling :meth:`.finish` to clean up resources. Sets
        :attr:`.started` to `False`.
        """
        self.logger.info('Closing: {}'.format(self))
        self.finish()
        self.started = False

    def finish(self):
        """
        Clean up resources. To be overridden by subclasses.
        """
        pass

    @abc.abstractmethod
    def process(self, num, state):
        """
        Process the model state to create export

        Args:
            num (int): an index for the `state`
            state (dict): a model snapshot

        """
        self.logger.debug('Processing step #{}'.format(num))

    def get_info(self):
        """
        Returns:
            dict: basic metadata about self (exports, version and cls)
        """
        return dict(exports=self._exports_, version=self.__version__, cls=self.__class__.__name__)
