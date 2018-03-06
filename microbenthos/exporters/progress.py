"""
Exporter that shows the  simulation progress bar on the console
"""

import logging

import tqdm
from fipy import PhysicalField

from .exporter import BaseExporter


class ProgressExporter(BaseExporter):
    _exports_ = 'progress'
    __version__ = '2.0'
    is_eager = True

    def __init__(self, desc = 'evolution', position = None, **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(ProgressExporter, self).__init__(**kwargs)

        self._pbar = None
        self._desc = desc
        self._total_time = None
        self._position = position

    def prepare(self, sim):
        """
        Set up the progress bar
        """
        self.logger.debug('Preparing progressbar for simulation: {} {} {}'.format(
            sim.simtime_total, sim.simtime_step, sim.total_steps
            ))
        self._total_time = sim.simtime_total
        self._total_time_value = self._total_time.value
        self._total_time_unit = self._total_time.unit.name()

        self._max_sweeps = sim.max_sweeps

        self._pbar = tqdm.tqdm(
            total=int(self._total_time.numericValue),
            desc=self._desc,
            unit='dt',
            dynamic_ncols=True,
            position=self._position,
            )
        # self._pbar = tqdm.tqdm(total=sim.total_steps, desc=self._desc)

    def process(self, num, state):
        time, tdict = state['time']['data']
        curr = PhysicalField(time, tdict['unit']).inUnitsOf(self._total_time.unit)
        dt = int(curr.numericValue) - self._pbar.n  # in seconds
        self._pbar.update(dt)

        clock_info = '{0:.2f}/{1:.2f} {2}'.format(
            float(curr.value),
            float(self._total_time_value),
            self._total_time_unit,
            )

        residual = state['metrics']['residuals']['data'][0]
        sweeps = state['metrics']['sweeps']['data'][0]
        # sweeps = state['metrics']['calc_times']['data'][0]

        self._pbar.set_postfix(
            clock=clock_info,
            dt=dt,
            res=residual,
            sweeps='{}/{}'.format(sweeps, self._max_sweeps)
            )

    def finish(self):
        self._pbar.close()
