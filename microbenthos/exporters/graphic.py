import logging
import os

from matplotlib import animation

from . import BaseExporter
from ..dataview import SnapshotModelData, ModelPlotter


class GraphicExporter(BaseExporter):
    """
    A 'stateless' exporter for model snapshot data into HDF file. The exporter only keeps the
    output path, and reopens the file for each snapshot. This ensures that each snapshot is
    committed to disk, reducing risk of data corruption. It uses :func:`save_snapshot` internally.
    """
    _exports_ = 'graphic'
    __version__ = '2.1'

    def __init__(self, show = False, write_video = False, video_dpi = 200, filename =
    'simulation.mp4', track_budget = False, **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(GraphicExporter, self).__init__(**kwargs)

        self.show = show
        self._filename = filename
        self.writer = None
        self.write_video = bool(write_video)
        self.video_dpi = int(video_dpi)
        self.track_budget = track_budget

    @property
    def outpath(self):
        return os.path.join(self.output_dir, self._filename)

    def prepare(self, sim):
        """
        Prepare the graphic exporter. Primarily to show a live ticker plot of the simulation,
        and optionally to write it into a video.

        See: :meth:`BaseExporter.prepare`.

        """
        self.logger.info('Preparing graphic exporter')
        self.mdata = SnapshotModelData()
        self.plot = ModelPlotter(model=self.mdata, track_budget=self.track_budget)

        if self.write_video:
            Writer = animation.writers['ffmpeg']

            self.writer = Writer(fps=15, bitrate=1800,
                                 metadata=dict(
                                     artist='Microbenthos - Arjun Chennu',
                                     copyright='2018')
                                 )
            self.logger.debug('Created video writer {}: dpi={}'.format(self.writer, self.video_dpi))

    def process(self, num, state):
        """
        Process the simulation step for graphical export

        Args:
            num (int): The step number
            state (dict): The model snapshot
        """

        self.logger.debug('Processing snapshot #{}'.format(num))

        self.mdata.store = state

        if num == 0:
            self.plot.setup_model()
            if self.write_video:
                self.writer.setup(self.plot.fig, self.outpath, dpi=self.video_dpi)

            if self.show:
                self.plot.show()

        self.plot.update_artists(tidx=0)
        self.plot.draw()

        if self.writer:
            self.writer.grab_frame()

    def finish(self):
        """
        Clean up exporter resources
        """
        if self.writer:
            self.logger.debug('Finishing writer')
            self.writer.finish()

        self.plot.close()
        del self.plot
