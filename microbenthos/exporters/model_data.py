import logging
import os

import h5py as hdf

from . import BaseExporter
from ._output_dir_mixin import OutputDirMixin
from ..model import save_snapshot


class ModelDataExporter(OutputDirMixin, BaseExporter):
    """
    A 'stateless' exporter for model snapshot data into HDF file. The exporter only keeps the
    output path, and reopens the file for each snapshot. This ensures that each snapshot is
    committed to disk, reducing risk of data corruption. It uses :func:`.save_snapshot` internally.
    """
    _exports_ = 'model_data'
    __version__ = '2.1'

    def __init__(self, overwrite = False,
                 filename = 'simulation_data.h5',
                 compression = 6,
                 **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(ModelDataExporter, self).__init__(**kwargs)

        self.overwrite = overwrite
        self._filename = str(filename)
        self._compression = int(compression)
        assert 0 <= self._compression <= 9

    @property
    def outpath(self):
        return os.path.join(self.output_dir, self._filename)

    def prepare(self, state):
        """
        Check that the output path can be created. Create the HDF file and
        add some metadata from the exporter.

        If newly created, then the `state` is stored into the disk.

        Warnings:
            If the output file already exists on disk, then it is just appended to. So, care must
            be taken by the caller that old files are removed, if so desired.

        """
        self.logger.debug('Preparing file for export')

        self.output_dir = self.runner.output_dir

        # if no file exists, then save the first state
        exists = os.path.exists(self.outpath)

        with hdf.File(self.outpath, 'a', libver='latest') as hf:
            hf.attrs.update(self.get_info())

        if not exists:
            save_snapshot(self.outpath, snapshot=state,
                          compression=self._compression)

        self.logger.debug('Preparation done')

    def process(self, num, state):
        """
        Append the `state` to the HDF store.

        """
        self.logger.debug('Processing export data for step #{}'.format(num))
        save_snapshot(self.outpath, snapshot=state,
                      compression=self._compression)
        self.logger.debug('Export data processed')
