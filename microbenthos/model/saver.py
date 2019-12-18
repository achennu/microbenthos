"""
Implements a data saver for model snapshots
"""

import logging
from collections.abc import Mapping

import h5py as hdf
from fipy.tools import numerix as np


def save_snapshot(fpath, snapshot, compression = 6, shuffle = True):
    """
    Save a snapshot dictionary of the model to a HDF file

    This method preserves the nested structure of the model snapshot. If the specified file path
    already exists, then the snapshot data is recursively appended to the nested
    data structure within.

    The nested data structure has three keys with special meaning:

    * ``"metadata"``
        The dictionary under this key will be saved as HDF attributes of the group it is in.

    * ``"data"``
        The value here is expected to be a tuple `(data_array, meta_dict)`, and is saved
        as a HDF dataset with the attributes set from the `meta_dict`. This dataset
        will be appended to if future snapshots are appended to the file.

    * ``"data_static"``
        This is similar to the `data` case, except it is for data that does not change during
        model evolution. So a fixed-size dataset called "data" is created here.


    Note:
         Due to the recursive traversal of the snapshot, no guarantees are made that the data
         saving is done atomically for the dictionary. As far as possible, the file access is
         brief and done under a closing context of :class:`h5py:File`.

         Also, nested snapshot dictionaries with infinite self references in nodes will be
         problematic.

    Args:
        fpath (str): Path to the target HDF :class:`h5py:File`

        snapshot (dict): Nested snapshot dictionary

        compression (int): The compression level 0-9 for the created :class:`h5py:Dataset`
            (default: 6)

        shuffle (bool): Whether to use the shuffle filter

    Raises:
        TypeError: if `snapshot` is not a suitable mapping type
        ValueError: if saving fails due to incompatible data types

    """
    logger = logging.getLogger(__name__)

    if not snapshot:
        logger.debug('Empty snapshot received')
        return

    if not isinstance(snapshot, Mapping):
        logger.error('Snapshot object should be a mapping like dict, not {}'.format(type(snapshot)))

    fpath = str(fpath)

    logger.debug('Saving snapshot ({}) to {}'.format(snapshot.keys(), fpath))
    with hdf.File(fpath, libver='latest') as hf:
        _save_nested_dict(snapshot, hf, compression=compression, shuffle=shuffle)
    logger.debug('Snapshot saved in {}'.format(fpath))


def _save_nested_dict(D, root, **kwargs):
    """
    Recursively traverse the nested dictionary and save data and metadata into a mirrored hierarchy

    Args:
        D (dict): A possibly nested dictionary with special keys
        root (:class:`h5py:Group`): Reference to a node within the state hierarchy

    """
    logger = logging.getLogger(__name__)
    logger.debug('Saving to root: {}'.format(root))
    path = root.name

    if not isinstance(D, Mapping):
        raise TypeError('Expected (nested) dict, but got {}'.format(type(D)))

    D = D.copy()

    meta = D.pop('metadata', None)
    if meta:
        if not isinstance(meta, Mapping):
            raise ValueError(
                '"metadata" should be mapping, not {}. In path: {}'.format(type(meta), path))

        logger.debug('Saving {}:metadata'.format(path))
        for metak, metav in meta.items():
            if (metav is not None) and (metak not in root.attrs):
                root.attrs[metak] = metav
            else:
                logger.debug('Skipping metadata {}.{} = {}'.format(path, metak, metav))

    data = D.pop('data', None)
    if data:
        try:
            dsdata, dsmeta = data
            dsdata = np.asarray(dsdata)
        except:
            logger.error('Improper {}.data: {}'.format(path, data))
            raise ValueError(
                '"data" should be a (array, meta_dict) sequence. In path: {}'.format(path))

        logger.debug('data at {}'.format(path))
        # logger.debug('data shape={} dtype={}'.format(dsdata.shape, dsdata.dtype))
        # logger.debug('data:metadata: {}'.format(dsmeta))
        try:
            _save_data(root, dsdata, dsmeta, name='data', **kwargs)
        except IOError:
            logger.error('Error saving {} data {}: {}'.format(root, root['data'], dsdata.shape))
            raise

    stdata = D.pop('data_static', None)
    if stdata:
        try:
            dsstdata, dsstmeta = stdata
        except:
            logger.error('Improper {}.data_static: {}'.format(path, stdata))
            raise ValueError(
                '"data_static" should be a (array, meta_dict) sequence. In path: {}'.format(path))

        logger.debug('data_static at {}'.format(path))
        logger.debug('data_static shape={} dtype={}'.format(dsstdata.shape, dsstdata.dtype))

        if 'data' not in root:
            ds = root.create_dataset('data',
                                     data=dsstdata,
                                     **kwargs
                                     )
            if dsstmeta:
                ds.attrs.update(dsstmeta)

    # now traverse the rest of the keys which are not popped
    for k in D:
        grp = root.require_group(k)
        _save_nested_dict(D[k], grp, **kwargs)


def _save_data(root, data, meta, name = 'data', **kwargs):
    """
    Commit the data to the `root` node under the given `name`, and resize the target
    :class:`h5py:Dataset` accordingly. The dataset is created, if it doesn't exist.
    """
    if 'data' not in root:
        maxshape = (None,) + data.shape
        chunks = (5,) + tuple([25 for _ in range(len(data.shape))])
        ds = root.create_dataset(name,
                                 shape=(1,) + data.shape,
                                 maxshape=maxshape,
                                 chunks=chunks,
                                 **kwargs
                                 )
        ds[0] = data
        if meta:
            ds.attrs.update(meta)

    else:
        ds = root['data']
        ds.resize(ds.shape[0] + 1, axis=0)
        ds[-1] = data
