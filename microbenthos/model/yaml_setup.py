
import yaml
from fipy import PhysicalField


def unit_constructor(loader, node):

    value = loader.construct_scalar(node)
    if isinstance(value, (str, unicode)):
        ret = PhysicalField(str(value))
    elif isinstance(value, (tuple, list)):
        ret = PhysicalField(*value)
    else:
        raise ValueError('Unknown input for PhysicalField: {} (type: {})'.format(value, type(value)))
    return ret


def unit_representer(dumper, data):
    return dumper.represent_scalar(u"!unit", u"%s" % str(data))

yaml.add_constructor(u"!unit", unit_constructor)
yaml.add_representer(PhysicalField, unit_representer)
