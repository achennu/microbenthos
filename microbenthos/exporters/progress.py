"""
Exporter that shows the  simulation progress bar on the console
"""

import logging
import tqdm
from .exporter import BaseExporter

class ProgressExporter(BaseExporter):
    _exports_ = 'progress'
    __version__ = '1.0'

    def __init__(self, desc='evolution', **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(ProgressExporter, self).__init__(**kwargs)

        self._pbar = None
        self._desc = desc

    def prepare(self, sim):
        """
        Set up the progress bar
        """
        self.logger.error('SIMULATION {} {} {}'.format(
            sim.simtime_total, sim.simtime_step, sim.total_steps
            ))
        self._pbar = tqdm.tqdm(total=sim.total_steps, desc=self._desc)

    def process(self, num, state):
        self._pbar.update()

    def finish(self):
        self._pbar.close()
