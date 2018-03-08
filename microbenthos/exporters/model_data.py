import logging
import os

import h5py as hdf

from . import BaseExporter
from ..model import save_snapshot


class ModelDataExporter(BaseExporter):
    """
    A 'stateless' exporter for model snapshot data into HDF file. The exporter only keeps the
    output path, and reopens the file for each snapshot. This ensures that each snapshot is
    committed to disk, reducing risk of data corruption. It uses :func:`save_snapshot` internally.
    """
    _exports_ = 'model_data'
    __version__ = '2.0'

    def __init__(self, overwrite = False, filename = 'simulation_data.h5', compression = 6,
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

    def prepare(self, sim):
        """
        Check that the output path can be created. Create the HDF file and
        add some metadata from the exporter.

        Args:
            sim: The Simulation object

        """
        self.logger.debug('Preparing file for export')

        if os.path.exists(self.outpath):
            if self.overwrite:
                self.logger.warning(
                    'Overwrite set for output file: {}'.format(self.outpath)
                )
                os.remove(self.outpath)
            else:
                # raise ValueError('Overwrite is false but output path
                # exists: {}'.format(self.outpath))
                self.logger.info(
                    'Data output file exists. Data series will be continued')

        with hdf.File(self.outpath, libver='latest') as hf:
            hf.attrs.update(self.get_info())

        self.logger.debug('Preparation done')

    def process(self, num, state):
        """
        Process the data to be exported

        Args:
            num (int): The step number of simulation evolution
            state (dict): The model snapshot state

        """
        self.logger.debug('Processing export data for step #{}'.format(num))
        save_snapshot(self.outpath, snapshot=state,
                      compression=self._compression)
        self.logger.debug('Export data processed')

    def finish(self):
        pass

