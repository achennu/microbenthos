import h5py as hdf
from fipy import PhysicalField

from .base import ModelData


class HDFModelData(ModelData):
    """
    Class that encapsulates the model data stored in a HDF :class:`h5py:Group`.
    """

    def check_store(self, obj):
        return isinstance(obj, hdf.Group)

    def get_node(self, path):
        """
        Return the node at the given path

        Args:
            path (str): A "/" separated path

        Returns:
            :class:`h5py:Group` or :class:`h5py:Dataset` stored at `path`

        Raises:
            KeyError: if no such node exists
        """
        self.logger.debug('Looking for node path: {}'.format(path))
        return self.store[path]

    def read_data_from(self, path, tidx=None):
        """
        Read out the data in `path` (a :class:`h5py:Dataset`) into a :class:`PhysicalField`

        If `tidx` is `None`, then no slicing of the dataset is done

        """
        path = path.replace('.', '/')

        if not path.endswith('/data'):
            path += '/data'
        ds = self.store[path]
        try:
            ds.id.refresh()
        except AttributeError:
            pass

        self.logger.debug('Found {}: {}'.format(path, ds))
        ds_unit = str(ds.attrs['unit'])
        if tidx is None:
            return PhysicalField(ds, ds_unit)
        else:
            return PhysicalField(ds[tidx], ds_unit)

    def read_metadata_from(self, path):
        """
        Return a dict-like (:class:`h5py:AttributeManager`) view of the metadata at `path`
        """
        path = path.replace('.', '/')
        node = self.store[path]
        return node.attrs
