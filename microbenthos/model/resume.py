"""
Module to implement the resumption of a simulation run.

The assumption is that a model object is created, and a HDF data store is available.
"""
import logging
from collections import Mapping

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
          AssertionError: if the structures are not compatible
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

        print('')
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
                logger.info('metadata {}::{} state={} store={}'.format(path, k, v, sv))
                assert v == sv, '{}: {} & {} are not equal'.format(path, v, sv)

        elif ctype in ('data', 'data_static'):

            logger.info('{}::data comparison'.format(path))
            node = node['data']

            state_arr, attrs = content
            # state_arr = np.asarray(state_arr)

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
                    raise

                logger.debug('{} state: {} & store: {}'.format(path, state_arr.shape, node.shape))

                if len(state_arr.shape) == 0:
                    logger.debug('{} skipped because single timepoint'.format(path))

                elif len(state_arr.shape) == 1:
                    assert state_arr.shape[0] == Ndepths
                    assert node.shape[0] == Ntime

                else:
                    raise NotImplementedError('Handling of state ararys of dim >=2')


        else:
            raise ValueError('Unknown return type: {}'.format(ctype))


def _iter_nested(state, path = None):
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
            raise ValueError('unknown node type in nested structure')

        path.pop(-1)
