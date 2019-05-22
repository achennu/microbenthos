from collections.abc import Mapping

from fipy import PhysicalField
from fipy.tools import numerix as np

from .base import ModelData


class SnapshotModelData(ModelData):
    """
        Class that encapsulates the model data stored in snapshot :class:`dict`
        """
    def check_store(self, obj):
        return isinstance(obj, Mapping)

    def get_node(self, path):
        parts = filter(None, path.split('/'))
        self.logger.debug('Looking for node path: {}'.format(parts))
        S = self.store
        for part in parts:
            S = S[part]
        self.logger.debug('Got node: {} with keys: {}'.format(path, S.keys()))
        return S

    def read_metadata_from(self, path):
        node = self.get_node(path)
        return node['metadata']

    def read_data_from(self, path, tidx = None):
        """
        Get the data from the path in the snapshot

        Args:
            path (str): Input used for :meth:`.get_node`
            tidx (None): This is ignored, since a model snapshot only contains one timepoint

        Returns:
            a :class:`PhysicalField` of the data with units at the node

        """
        self.logger.debug('Getting data from {}'.format(path))
        node = self.get_node(path)

        try:
            data, meta = node['data']
        except KeyError:
            try:
                data, meta = node['data_static']
            except KeyError:
                self.logger.error('Could not find "data" or "data_static" in {}'.format(path))
                raise ValueError('Path {} does not exist in snapshot'.format(path))

        unit = meta['unit']

        # if tidx is None:
        #   return PhysicalField(np.atleast_1d(data), unit)
        # else:
        #     return PhysicalField(np.atleast_1d(data[tidx]), unit)

        return PhysicalField(np.atleast_1d(data), unit)
