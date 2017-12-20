import logging
import os
import cerberus
from fipy import PhysicalField
from sympy import sympify, Symbol

logger = logging.getLogger(__name__)

class ModelSchemaValidator(cerberus.Validator):

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
        try:
            a, b = value.rsplit('.', 1)
            return True
        except ValueError:
            return not value.startswith('.')

    def _validate_type_physical_unit(self, value):
        """ Enables validation for `unit` schema attribute.
        :param value: field value.
        """
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
        try:
            e = sympify(value)
            return True
        except:
            return False

    def _validate_type_symbolable(self, value):
        """
        String that can be run through sympify and only has one variable symbol in it.
        """
        try:
            e = sympify(value)
            return isinstance(e, Symbol)
        except:
            return False



from .yaml_loader import yaml


def from_yaml(fpath, from_schema=None):
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
        model_schema = yaml.load(fp)#['model_schema']

    return model_schema



