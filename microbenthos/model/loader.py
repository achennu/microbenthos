import logging
import os

import cerberus
from fipy import PhysicalField
from sympy import sympify, Symbol
from .yaml_setup import yaml


class ModelSchemaValidator(cerberus.Validator):
    logger = logging.getLogger(__name__)

    # def __init__(self, *args, **kwargs):
    #     # self.logger.propagate = False
    #     super(ModelSchemaValidator, self).__init__(*args, **kwargs)

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
            a, b = value.rsplit('.', 1)
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
        except:
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
        try:
            e = sympify(value)
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
        Validate that the value of the field is like_store
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
        if value in ('env', 'domain'):
            return

        elif value.startswith('microbes'):
            mtargets = ('features', 'processes')
            parts = value.split('.')

            try:
                if len(parts) == 2:
                    if (parts[0] == 'microbes') and (parts[-1] not in mtargets):
                        return
                    else:
                        raise ValueError

                elif len(parts) == 3:
                    if (parts[0] == 'microbes') and (parts[1] not in mtargets) and \
                            (parts[2] in mtargets):
                        return
                    else:
                        raise ValueError

            except ValueError:
                self._error(field,
                            'Microbes store must be of form "microbes.xyz" or "microbes.xyz.F" '
                            'where F in (processes, fields). Invalid: {}'.format(
                                value))

        else:
            self._error(field, 'Store must be "domain", "env" or "microbes" store, '
                               'not {}'.format(value))


def from_yaml(fpath, from_schema = None):
    logger = logging.getLogger(__name__)
    logger.info('Loading model from: {}'.format(fpath))
    with open(fpath) as fp:
        model_dict = yaml.load(fp)

    INBUILT = os.path.join(os.path.dirname(__file__), 'schema.yml')
    from_schema = from_schema or INBUILT
    logger.debug('Using schema: {}'.format(from_schema))
    with open(from_schema) as fp:
        model_schema = yaml.load(fp)['model_schema']

    validator = ModelSchemaValidator()

    valid_model = validator.validated(model_dict, model_schema)
    if not valid_model:
        logger.error('Model definition not validated!')

        logger.error(validator.errors)

        raise ValueError('Model definition improper!')
    else:
        logger.info('Model definition successfully loaded: {}'.format(valid_model.keys()))
        return valid_model


def get_model_schema():
    """
    Returns the inbuilt model schema
    """
    INBUILT = os.path.join(os.path.dirname(__file__), 'schema.yml')
    with open(INBUILT) as fp:
        model_schema = yaml.load(fp)  # ['model_schema']

    return model_schema
