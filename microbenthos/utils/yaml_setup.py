"""
Imports yaml from PyYaml and adds serialization options for :class:`fipy.PhysicalField`.
"""
from __future__ import unicode_literals
import yaml
from fipy import PhysicalField


# import ruamel.yaml
# class PhysicalField_(PhysicalField):
#     yaml_tag = u'!unit'
#
#     @classmethod
#     def validate_yaml(cls, constructor, node):
#         value = node.value
#         if isinstance(value, (str, unicode)):
#             ret = PhysicalField(str(value))
#         elif isinstance(value, (tuple, list)):
#             ret = PhysicalField(*value)
#         else:
#             raise ValueError(
#                 'Unknown input for PhysicalField: {} (type: {})'.format(value, type(value)))
#         return ret
#
#     @classmethod
#     def to_yaml(cls, representer, node):
#         return representer.represent_scalar(cls.yaml_tag, str(node))
#
# yaml = ruamel.yaml.YAML()
# yaml.register_class(PhysicalField_)
def unit_constructor(loader, node):

    value = loader.construct_scalar(node)
    if isinstance(value, str):
        ret = PhysicalField(str(value))
    elif isinstance(value, (tuple, list)):
        ret = PhysicalField(*value)
    else:
        raise ValueError('Unknown input for PhysicalField: {} (type: {})'.format(value, type(value)))
    return ret


def unit_representer(dumper, data):
    return dumper.represent_scalar(u"!unit", u"%s" % str(data))


yaml.UnsafeLoader.add_constructor(u"!unit", unit_constructor)
yaml.Dumper.add_representer(PhysicalField, unit_representer)
