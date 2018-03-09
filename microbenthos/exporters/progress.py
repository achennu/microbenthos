"""
Exporter that shows the  simulation progress bar on the console
"""

import logging

import tqdm
from fipy import PhysicalField

from .exporter import BaseExporter


class ProgressExporter(BaseExporter):
    _exports_ = 'progress'
    __version__ = '4.0'
    is_eager = True

    def __init__(self, desc='evolution', position=None, **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(ProgressExporter, self).__init__(**kwargs)

        self._pbar = None
        self._desc = desc
        self._total_time = None
        self._position = position

    def prepare(self, state):
        """
        Set up the progress bar
        """
        sim = self.sim
        self.logger.debug('Preparing progressbar for simulation: {}'.format(sim.simtime_total))

        self._pbar = tqdm.tqdm(
            total=int(sim.simtime_total.numericValue),
            desc=self._desc,
            unit='dt',
            dynamic_ncols=True,
            position=self._position,
            initial=int(sim.model.clock.numericValue),
        )

    def process(self, num, state):
        simtime_total = self.sim.simtime_total

        time, tdict = state['time']['data']
        curr = PhysicalField(time, tdict['unit']).inUnitsOf(simtime_total.unit)
        dt = curr.numericValue - self._pbar.n  # in seconds

        clock_info = '{0:.2f}/{1:.2f} {2}'.format(
            float(curr.value),
            float(simtime_total.value),
            simtime_total.unit.name(),
        )

        residual = state['metrics']['residual']['data'][0]
        sweeps = state['metrics']['num_sweeps']['data'][0]

        self._pbar.set_postfix(
            clock=clock_info,
            dt=dt,
            res='{:.2g} / {:.2g}'.format(residual, self.sim.residual_target),
            sweeps='{:02d}/{:3.2f} <={}'.format(
                sweeps,
                self.sim.recent_sweeps,
                self.sim.max_sweeps
            )
        )
        self._pbar.update(int(dt))

    def finish(self):
        self._pbar.close()
