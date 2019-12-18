import copy
import io
import logging
from collections.abc import Mapping

from .loader import validate_yaml, validate_dict


class CreateMixin(object):
    """
    A Mixin class that can create instances of classes defined in schema.yml, based on the
    :attr:`.schema_key`. A variety of object types are handled in :meth:`.create_from`,
    and the validated input is stored as :attr:`.definition_`
    """
    @classmethod
    def create_from(cls, obj, **kwargs):
        """
        Instantiate class from the given object, and if possible, save the definition that was
        used to create the instance.

        Args:
            obj (object, dict, str, :class:`~io.IOBase`):
                * :class:`object`: if an instance of the cls, then it is returned directly
                * :class:`dict`: if a mapping, then it is passed to :func:`.validate_dict`
                * str: if a string, it is converted to stream-like and passed to
                  :func:`validate_yaml`
                * :class:`io.IOBase`: if a stream, it is passed to :py:func:`validate_yaml`

            **kwargs: passed to :meth:`validate_dict` or :meth:`validate_yaml` as necessary.

        Attributes:
            `definition_` : the validated definition used to create the instance

        Returns:
            instance of the class this is subclassed by

        """
        logger = logging.getLogger(__name__)
        logger.debug('Creating instance of {} from {}'.format(cls, type(obj)))

        if kwargs.get('key') is None:
            kwargs['key'] = cls.schema_key

        if isinstance(obj, cls):
            obj.definition_ = None
            return obj

        if isinstance(obj, Mapping):
            definition = validate_dict(obj, **kwargs)

        elif isinstance(obj, str):
            definition = validate_yaml(
                io.StringIO(obj), **kwargs)

        elif isinstance(obj, (io.IOBase, file)):
            # a file-like object
            definition = validate_yaml(obj, **kwargs)

        else:
            raise NotImplementedError('Unknown type {} to create {} from'.format(type(obj), cls))

        definition_ = copy.deepcopy(definition)
        inst = cls(**definition)
        inst.definition_ = definition_
        return inst
