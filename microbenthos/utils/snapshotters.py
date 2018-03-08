import h5py as hdf
from fipy import Variable, PhysicalField
from fipy.terms.binaryTerm import _BinaryTerm
from fipy.tools import numerix as np


def snapshot_var(V, base = False, to_unit = None):
    """
    Utility to express a variable array as its numeric value and corresponding units

    Args:
        V (PhysicalField, Variable, CellVariable, binOp, np.ndarray, int, float): The variable
        base (bool): Whether to express in base units
        to_unit (str): Return array in these units. Ignored if `base = True`

    Returns:
        Tuple of (array, dict(unit=unit))

    """
    if isinstance(V, (PhysicalField, Variable, _BinaryTerm)):
        # This should also cover fipy.CellVariable and fipy.variables.binaryOperatorVariable.binOp
        Vunit = V.unit.name()
        try:
            if base:
                var = V.inBaseUnits()
            else:
                if to_unit:
                    var = V.inUnitsOf(to_unit)
                else:
                    var = V.inUnitsOf(V.unit)
        except:
            import logging
            logger = logging.getLogger(__name__)
            logger.error('V={!r} could not be expressed in units: {}'.format(V, V.unit),
                         exc_info=True)
            raise

        if Vunit != '1':
            unit = var.unit.name()
            arr = np.array(var.value)

        else:
            arr = var
            unit = Vunit

    elif isinstance(V, np.ndarray):
        arr = V
        unit = '1'

    elif isinstance(V, (int, float)):
        arr = np.array(V)
        unit = '1'

    else:
        raise ValueError('Cannot snapshot variable of type {}'.format(type(V)))

    return arr, dict(unit=unit)


def restore_var(input, tidx):
    """
    This is the inverse operation of :func:`snapshot_var`. It takes the output of that function
    and returns a PhysicalField quantity


    Returns:
        :class:`PhysicalField`

    """
    if tidx is None:
        tidx = slice(None, None)

    if isinstance(input, hdf.Group):
        value = input['data']
        unitstr = value.attrs['unit']

    elif isinstance(input, (tuple, list)):
        value, mdict = input
        unitstr = mdict['unit']

    else:
        raise ValueError('Unknown type {} to restore data from'.format(type(input)))

    return PhysicalField(value[tidx], unit=unitstr)
