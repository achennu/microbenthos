"""
Module to implement the resumption of a simulation run.

The assumption is that a model object is created, and a HDF data store is available.
"""
import logging
from collections.abc import Mapping

import h5py as hdf
import numpy as np


def check_compatibility(state, store):
    """
    Check that the given model snapshot is compatible with the structure of the store. This
    checks that every path in the snapshot exists in the HDF store.

    Args:
        state (dict): a model snapshot dictionary
        store (:class:`~hdf.Group`): the root node of the stored model data

    Returns:
        True if the structures are compatible

    Raises:
          ValueError: if an incompatible data is returned
          NotImplementedError: for state arrays of dim > 1

    """
    logger = logging.getLogger(__name__)
    logger.info('Checking compatibility with {}'.format(store))

    time_ds = store['/time/data']
    depths_ds = store['/domain/depths/data']
    Ntime = len(time_ds)
    Ndepths = len(depths_ds)

    for path_parts, ctype, content in _iter_nested(state):

        path = '/' + '/'.join(path_parts)

        node = store[path]

        if ctype == 'metadata':
            ckeys = set(content.keys())
            skeys = set(node.attrs.keys())
            key_diff = skeys.difference(ckeys)
            if key_diff:
                logger.warning('{}::metadata has divergent keys: {}'.format(path, key_diff))
            for k, v in content.items():
                sv = node.attrs[k]
                if hasattr(sv, 'tolist'):
                    sv = sv.tolist()
                    if isinstance(sv, list):
                        sv = tuple(sv)
                logger.debug('metadata {}::{} state={} store={}'.format(path, k, v, sv))

                try:
                    is_equal = (set(v) == set(sv))
                except TypeError:
                    is_equal = (v == sv)
                finally:
                    if not is_equal:
                        raise ValueError(
                            '{}: {} & {} are not equal'.format(path, v, sv))

        elif ctype in ('data', 'data_static'):

            logger.debug('{}::data comparison'.format(path))
            node = node['data']

            state_arr, attrs = content

            if ctype == 'data_static':
                assert np.allclose(node, state_arr)

            elif node is time_ds:
                continue

            else:
                try:
                    assert len(node.shape) == len(state_arr.shape) + 1  # the time axis
                except AssertionError:
                    logger.warning('store: {} and state: {}'.format(
                        node.shape, state_arr.shape
                    ))
                    raise ValueError('Shape lengths of {} do not match: store={} state={}'.format(
                        path, node.shape, state_arr.shape
                    ))

                logger.debug('{} state: {} & store: {}'.format(path, state_arr.shape, node.shape))

                if len(state_arr.shape) == 0:
                    logger.debug('{} skipped because single timepoint'.format(path))

                elif len(state_arr.shape) == 1:
                    try:
                        assert state_arr.shape[0] == Ndepths
                        # assert node.shape[0] == Ntime
                    except AssertionError:
                        raise ValueError('{} shape did not match. state: {} stored: {}'.format(
                            path, state_arr.shape, node.shape))

                else:
                    raise NotImplementedError('Handling of state ararys of dim >=2')

        else:
            raise ValueError('Unknown return type: {}'.format(ctype))


def _iter_nested(state, path=None):
    if path is None:
        path = []

    RESERVED = ('metadata', 'data', 'data_static')

    for rtype in RESERVED:
        obj = state.get(rtype)
        if obj:
            yield (path, rtype, obj)

    for key in state:
        if key in RESERVED:
            continue

        path.append(key)
        val = state[key]

        if isinstance(val, Mapping):
            for item in _iter_nested(val, path):
                yield item

        else:
            print('Got type {}={} at {}. What todo?'.format(key, type(val), path))
            raise TypeError('unknown node type in nested structure')

        path.pop(-1)


def truncate_model_data(store, time_idx):
    """
    Truncates the model data in store till the `time_idx` along the time axis.

    Warning:
        This is a destructive operation on the provided `store`, if it is write-enabled. Use with
        caution, because it will resize the datasets in the store to the extent determined by
        `time_idx` and all the data beyond that will be lost. Only in the case of `time_idx =
        -1`, may there be no data loss as the resize will occur to the same size as the time vector.

    Args:
        store (:class:`hdf.Group`): root store of the model data (should be writable)
        time_idx (int): An integer indicating that index of the time point to truncate

    Returns:
        size (int): the size of the time dimension after truncation
    """
    logger = logging.getLogger(__name__)
    # now truncate the time-dependent datasets to the time-index
    # if a ds has shape (35, 210), it means 35 time points
    # time_idx uses the python scheme for indexing, that is 0 is start, -1 is end, etc
    dsize = len(store['/time/data'])
    if dsize == 0:
        logger.error('Store had a zero-length time series! Cannot use this store.')
        return 0

    tsize = ((dsize + 1 + time_idx) % dsize) or dsize
    logger.warning('Truncating datasets time-dim from {} to  {}'.format(dsize, tsize))
    assert tsize > 0

    def truncate_temporal_dataset(name, ds):
        if isinstance(ds, hdf.Dataset):
            if name.startswith('domain/'):
                return
            if ds.shape[0] != tsize:
                ds.resize(tsize, axis=0)
                logger.debug('{} truncated from {} to {}'.format(name, ds.shape[0], tsize))
            else:
                logger.debug('{} truncation skipped due to same size'.format(name))

    # now walk over the hdf hierarchy and resize suitable arrays
    store.visititems(truncate_temporal_dataset)

    return tsize
