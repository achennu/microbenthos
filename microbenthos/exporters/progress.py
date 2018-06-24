import logging

import tqdm
from fipy import PhysicalField

from .exporter import BaseExporter


class ProgressExporter(BaseExporter):
    """
    An exporter that displays a progress bar of a running simulation.
    """
    _exports_ = 'progress'
    __version__ = '5.0'
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

    def prepare(self, state):
        """
        Set up the progress bar
        """
        sim = self.sim
        self.logger.debug('Preparing progressbar for simulation: {}'.format(sim.simtime_total))
        self._clock_unit = sim.simtime_total.unit
        self._prev_t = sim.model.clock.inUnitsOf(self._clock_unit)

        self._pbar = tqdm.tqdm(
            total=round(sim.simtime_total.value, 2),
            desc=self._desc,
            # unit=self._clock_unit.name(),
            dynamic_ncols=True,
            position=self._position,
            initial=round(self._prev_t.value, 2),
            leave=True,
            )

    def srepr(self, v, prec = 2):
        unit = v.unit.name()
        return '{:.{}f} {}'.format(float(v.value), prec, unit)

    def process(self, num, state):
        """
        Write the progress information to the progress bar

        This includes info about residual, duration (dt), and number of sweeps in the timestep
        and the global progress through the model clock.
        """

        time, tdict = state['time']['data']
        # curr = PhysicalField(time, tdict['unit']).inUnitsOf(simtime_total.unit)
        curr = PhysicalField(time, tdict['unit']).inUnitsOf(self._clock_unit)
        dt = curr - self._prev_t
        dt_unitless = round((curr - self._prev_t).value, 2)

        # clock_info = '{0:.2f}/{1:.2f} {2}'.format(
        #     float(curr.value),
        #     float(simtime_total.value),
        #     simtime_total.unit.name(),
        # )

        residual = state['metrics']['residual']['data'][0]
        sweeps = state['metrics']['num_sweeps']['data'][0]

        self._pbar.set_postfix(
            # clock=clock_info,
            dt=self.srepr(dt.inUnitsOf('s')),
            res='{:.2g} / {:.2g}'.format(residual, self.sim.residual_target),
            sweeps='{:02d}/{:3.2f}'.format(
                sweeps,
                # self.sim.recent_sweeps,
                self.sim.max_sweeps
                )
            )
        self._pbar.update(round(dt_unitless, 2))
        self._prev_t = curr

    def finish(self):
        self._pbar.close()
