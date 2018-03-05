"""
Base class definition for exporters
"""

import abc
import logging
import os

# from ..utils import CreateMixin


class BaseExporter(object):
    __metaclass__ = abc.ABCMeta
    _exports_ = ''
    __version__ = ''
    is_eager = False

    def __init__(self, name='exp', logger = None):

        if not logger:
            self.logger = logging.getLogger(__name__)
            self.logger.warning('No logger supplied, creating in base class: {}'.format(__name__))
        else:
            self.logger = logger

        self.name = name

        if not self._exports_:
            raise ValueError('Exporter "_exports_" should not be empty')

        if not self.__version__:
            raise ValueError('Exporter "_exports_" should not be empty')

        self._output_dir = None
        self.started = False
        self.logger.info('{} info: {}'.format(self, self.get_info()))

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.name)

    def setup(self, runner):
        self.logger.debug('Setting up {}'.format(self))
        self.output_dir = runner.output_dir
        self.prepare(runner.simulation)
        self.started = True

    @abc.abstractmethod
    def prepare(self, sim):
        raise NotImplementedError('Should be implemented in subclass')

    @property
    def output_dir(self):
        return self._output_dir

    @output_dir.setter
    def output_dir(self, path):
        if os.path.isdir(path):
            self._output_dir = path
            self.logger.debug('output_dir set: {}'.format(self.output_dir))
        else:
            raise ValueError('Output directory does not exist')

    def close(self):
        self.logger.info('Closing: {}'.format(self))
        self.finish()
        self.started = False

    @abc.abstractmethod
    def finish(self):
        raise NotImplementedError('Should be implemented in subclass')

    @abc.abstractmethod
    def process(self, num, state):
        self.logger.debug('Processing step #{}'.format(num))
        self._process(num, state)

    def get_info(self):
        return dict(exports=self._exports_, version=self.__version__, cls=self.__class__.__name__)
