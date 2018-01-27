from fipy import Variable, PhysicalField
from fipy.tools import numerix


def snapshot_var(V, base = False, to_unit = None):
    """
    Utility to express a variable array as its numeric value and corresponding units

    Args:
        V (PhysicalField, Variable, CellVariable, binOp, array): The variable
        base (bool): Whether to express in base units
        to_unit (str): Return array in these units. Ignored if `base = True`

    Returns:
        Tuple of (array, dict(unit=unit))

    """
    if isinstance(V, (PhysicalField, Variable)):
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
            arr = numerix.array(var.value)

        else:
            arr = var
            unit = Vunit

    elif isinstance(V, numerix.ndarray):
        arr = V
        unit = '1'

    else:
        raise ValueError('Cannot snapshot variable of type {}'.format(type(V)))

    return arr, dict(unit=unit)
