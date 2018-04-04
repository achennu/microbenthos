import logging
import os

from fipy import PhysicalField
from matplotlib import animation

from . import BaseExporter
from ._output_dir_mixin import OutputDirMixin
from ..dataview import SnapshotModelData, ModelPlotter


class GraphicExporter(OutputDirMixin, BaseExporter):
    """
    An exporter for model snapshot data into a graphical representation.

    This can write out videos (with :attr:`write_video` = True) and image frames (with
    :attr:`.write_frames` = True). This uses :mod:`matplotlib` to render the plots.
    """
    _exports_ = 'graphic'
    __version__ = '3.0'

    def __init__(self, show = False,
                 write_video = False,
                 video_dpi = 100,
                 video_filename = 'simulation.mp4',
                 track_budget = False,
                 write_frames = False,
                 frames_dpi = 100,
                 frames_folder = 'frames',
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
        self.frames_dirname = str(frames_folder)

    @property
    def video_outpath(self):
        return os.path.join(self.output_dir, self._video_filename)

    @property
    def frames_outdir(self):
        return os.path.join(self.output_dir, self.frames_dirname)

    def prepare(self, state):
        """
        Prepare the :class:`.ModelPlotter` that will generate the plots for graphical export
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

            from datetime import datetime
            year = datetime.today().year

            self.writer = Writer(fps=10, bitrate=1400,
                                 metadata=dict(
                                     artist='MicroBenthos',
                                     copyright=str(year))
                                 )
            self.writer.setup(self.plot.fig, self.video_outpath, dpi=self.video_dpi)
            self.writer.grab_frame()
            self.logger.debug('Created video writer {}: dpi={}'.format(self.writer, self.video_dpi))

        if self.write_frames:
            try:
                os.makedirs(self.frames_outdir)
            except OSError:
                pass
            finally:
                assert os.path.isdir(self.frames_outdir)
                self.logger.debug('Created folder for frames: {}'.format(self.frames_outdir))
                self.write_frame(state)

    def process(self, num, state):
        """
        Update the model plotter and grab or write frames
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
        """
        Save a frame into the output directory for the current state
        """
        time, tdict = state['time']['data']
        clock = int(PhysicalField(time, tdict['unit']).numericValue)
        fname = 'frame_{:010d}.png'.format(clock)
        path = os.path.join(self.frames_outdir, fname)
        self.plot.fig.savefig(path)
        self.logger.debug('Wrote frame: {}'.format(fname))

    def finish(self):
        """
        Close the video writer and the model plotter.
        """
        if self.writer:
            self.logger.debug('Finishing writer')
            self.writer.finish()

        self.plot.close()
        del self.plot
