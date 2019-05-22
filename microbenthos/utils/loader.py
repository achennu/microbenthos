import logging
from collections.abc import Mapping

import cerberus
import pkg_resources
from fipy import PhysicalField
from sympy import sympify, Symbol

from .yaml_setup import yaml


# TODO: Allow equation with no diffusion term

class MicroBenthosSchemaValidator(cerberus.Validator):
    """
    A :mod:`cereberus` validator for schema.yml in MicroBenthos
    """
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    logger.propagate = False

    # def __init__(self, *args, **kwargs):
    #     # self.logger.propagate = False
    #     super(MicroBenthosSchemaValidator, self).__init__(*args, **kwargs)

    def _validate_type_importpath(self, value):
        """
        Validates if the value is a usable import path for an entity class

        Valid examples are:
            * pkg1.pkg2.mod1.class
            * class_name

        Invalid examples:
            * .class_name

        Args:
            value: A string

        Returns:
            True if valid
        """
        self.logger.debug('Validating importpath: {}'.format(value))
        try:
            _, __ = value.rsplit('.', 1)
            return True
        except ValueError:
            return not value.startswith('.')

    def _validate_type_physical_unit(self, value):
        """ Enables validation for `unit` schema attribute.
        :param value: field value.
        """
        self.logger.debug('Validating physical_unit: {}'.format(value))
        if isinstance(value, PhysicalField):
            if value.unit.name() != '1':
                return True

    def _validate_type_unit_name(self, value):
        """
        Checks that the string can be used as units
        Args:
            value:

        Returns:

        """
        self.logger.debug('Validating unit_name: {}'.format(value))
        try:
            PhysicalField(1, value)
            return True
        except TypeError:
            return False

    def _validate_like_unit(self, unit, field, value):
        """
        Test that the given value has compatible units

        Args:
            unit: A string useful with :class:`PhysicalField`
            field:
            value: An instance of a physical unit

        Returns:
            boolean if validated

        The rule's arguments are validated against this schema:
        {'type': 'string'}
        """
        self.logger.debug('Validating like_unit: {} {} {}'.format(unit, field, value))
        if not isinstance(value, PhysicalField):
            self._error(field, 'Must be a PhysicalField, not {}'.format(type(value)))

        try:
            value.inUnitsOf(unit)
        except:
            self._error(field, 'Must be compatible with units {}'.format(unit))

    def _validate_type_sympifyable(self, value):
        """
        A string that can be run through sympify
        """
        self.logger.debug('Validating sympifyable: {}'.format(value))
        if not isinstance(value, (str, int, float)):
            return False
        try:
            e = sympify(value)
            self.logger.debug('Sympified: {}'.format(e))
            return True
        except:
            return False

    def _validate_type_symbolable(self, value):
        """
        String that can be run through sympify and only has one variable symbol in it.
        """
        self.logger.debug('Validating symbolable: {}'.format(value))
        try:
            e = sympify(value)
            return isinstance(e, Symbol)
        except:
            return False

    def _validate_model_store(self, jnk, field, value):
        """
        Validate that the value of the field is a model store path

        Value should be of type:
            * domain.oxy
            * env.oxy.var
            * microbes.cyano.processes.oxyPS

        Args:
            unit:
            field:
            value:

        Returns:

        The rule's arguments are validated against this schema:
        {'type': 'string'}
        """
        self.logger.debug('Validating model_store={} for field {!r}: {!r}'.format(
            jnk, field, value
            ))

        if '.' not in value:
            self._error(field, 'Model store should be a dotted path, not {}'.format(value))

        parts = value.split('.')

        if not all([len(p) for p in parts]):
            self._error(field, 'Model store has empty path element: {}'.format(value))

        if parts[0] not in ('env', 'domain', 'microbes'):
            self._error(field, 'Model store root should be in (env, domain, microbes)')

        if parts[0] in ('domain', 'env'):
            pass

        elif parts[0] == 'microbes':
            mtargets = ('features', 'processes')

            if len(parts) < 4:
                self._error(field, 'Microbes model store needs atleast 4 path elements')

            if parts[2] not in mtargets:
                self._error(field, 'Microbes model store should be of type {}'.format(mtargets))

    def _normalize_coerce_float(self, value):
        return float(value)


def validate_yaml(stream, key = None, schema = None, schema_stream = None):
    logger = logging.getLogger(__name__)

    logger.info('Loading definition with yaml')

    inp_dict = yaml.unsafe_load(stream)
    if key:
        inp_dict = inp_dict[key]

    return validate_dict(inp_dict, key=key, schema=schema, schema_stream=schema_stream)


def validate_dict(inp_dict, key, schema = None, schema_stream = None):
    logger = logging.getLogger(__name__)

    logger.info('Loading definition from: {}'.format(inp_dict.keys()))

    logger.debug('Using schema key {!r} from schema_stream={}'.format(key, schema_stream))
    if schema is None:
        schema = get_schema(schema_stream=schema_stream)
    else:
        if not isinstance(schema, Mapping):
            raise TypeError('Supplied schema should be a mapping, not {!r}'.format(type(schema)))

    if key:
        schema = schema[key]
    logger.debug('Schema with entries: {}'.format(schema.keys()))

    validator = MicroBenthosSchemaValidator()

    validated = validator.validated(inp_dict, schema)

    if not validated:
        logger.propagate = True
        logger.error('Input definition not validated for schema {!r}!'.format(key))
        from pprint import pformat
        logger.warning(pformat(validator.errors))

        for path, errmsg in _denest_errors(validator.errors, [], []):
            logger.error('Error: {} :: {}'.format(path, errmsg))

        raise ValueError('Definition of {!r} invalid!'.format(key))

    else:
        logger.info('{} definition successfully loaded: {}'.format(key, validated.keys()))
        return validated


def _denest_errors(D, paths, all_items):
    for k in D:
        # print('descending into {}'.format(k))
        v = D[k]
        paths.append(k)
        for item in v:
            if isinstance(item, dict):
                _denest_errors(item, paths, all_items)
                if paths:
                    paths.pop(-1)

            elif isinstance(item, str):
                # full_path = '.'.join([str(_) for _ in paths])
                # print(f'{full_path}: {item}')
                all_items.append(('.'.join(str(_) for _ in paths), item))

            if paths:
                paths.pop(-1)

    return all_items


def get_schema(schema_stream = None):
    """
    Returns the inbuilt model schema
    """

    # INBUILT = pkg_resources.resource_stream(__name__, 'schema.yml')

    if schema_stream:
        schema = yaml.unsafe_load(schema_stream)
    else:
        with pkg_resources.resource_stream(__name__, 'schema.yml') as INBUILT:
            schema = yaml.unsafe_load(INBUILT)

    return schema


def find_subclasses_recursive(baseclass, subclasses = None):
    """
    Find subclasses recursively. `subclasses` should be a set into which to add the subclasses
    """
    if subclasses is None:
        subclasses = set()
    if not isinstance(baseclass, type):
        raise ValueError('Need a class, but received: {} of type {}'.format(
            baseclass, type(baseclass)))
    for sclass in baseclass.__subclasses__():
        subclasses.add(sclass)
        find_subclasses_recursive(sclass, subclasses)

    return subclasses
