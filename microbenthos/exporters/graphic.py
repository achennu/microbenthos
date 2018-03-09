import logging
import os

from fipy import PhysicalField
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
    __version__ = '3.0'

    def __init__(self, show=False,
                 write_video=False,
                 video_dpi=100,
                 video_filename='simulation.mp4',
                 track_budget=False,
                 write_frames=False,
                 frames_dpi=100,
                 frames_folder='frames',
                 **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(GraphicExporter, self).__init__(**kwargs)

        self.show = show
        self._video_filename = video_filename
        self.writer = None
        self.write_video = bool(write_video)
        self.video_dpi = int(video_dpi)
        self.track_budget = track_budget

        self.write_frames = bool(write_frames)
        self.frames_dpi = int(frames_dpi)
        self.frames_folder = str(frames_folder)

    def prepare(self, state):
        """
        Prepare the graphic exporter. Primarily to show a live ticker plot of the simulation,
        and optionally to write it into a video.

        See: :meth:`BaseExporter.prepare`.

        """
        self.logger.info('Preparing graphic exporter')
        self.mdata = SnapshotModelData()
        self.plot = ModelPlotter(model=self.mdata, track_budget=self.track_budget)

        self.mdata.store = state
        self.plot.setup_model()

        self.plot.draw()

        if self.show:
            self.plot.show()

        if self.write_video:
            Writer = animation.writers['ffmpeg']

            self.writer = Writer(fps=15, bitrate=1800,
                                 metadata=dict(
                                     artist='Microbenthos - Arjun Chennu',
                                     copyright='2018')
                                 )
            video_path = os.path.join(self.output_dir, self._video_filename)
            self.writer.setup(self.plot.fig, video_path, dpi=self.video_dpi)
            self.writer.grab_frame()
            self.logger.debug('Created video writer {}: dpi={}'.format(self.writer, self.video_dpi))

        if self.write_frames:
            frames_path = os.path.join(self.output_dir, self.frames_folder)
            try:
                os.makedirs(frames_path)
            except OSError:
                pass
            finally:
                assert os.path.isdir(frames_path)
                self.frames_path = frames_path
                self.logger.debug('Created folder for frames: {}'.format(frames_path))
                self.write_frame(state)

    def process(self, num, state):
        """
        Process the simulation step for graphical export

        Args:
            num (int): The step number
            state (dict): The model snapshot
        """

        self.logger.debug('Processing snapshot #{}'.format(num))

        self.mdata.store = state
        self.plot.update_artists(tidx=0)
        self.plot.draw()

        if self.writer:
            self.writer.grab_frame()

        if self.write_frames:
            self.write_frame(state)

    def write_frame(self, state):
        time, tdict = state['time']['data']
        clock = int(PhysicalField(time, tdict['unit']).numericValue)
        fname = 'frame_{:010d}.png'.format(clock)
        path = os.path.join(self.frames_path, fname)
        self.plot.fig.savefig(path)
        self.logger.debug('Wrote frame: {}'.format(fname))

    def finish(self):
        """
        Clean up exporter resources
        """
        if self.writer:
            self.logger.debug('Finishing writer')
            self.writer.finish()

        self.plot.close()
        del self.plot
