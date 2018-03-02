import copy
import io
import logging
from collections import Mapping

from .loader import validate_yaml, validate_dict


class CreateMixin(object):
    @classmethod
    def create_from(cls, obj, **kwargs):
        """
        Instantiate class from the given object

        Various types of `obj` are handled:
            * if obj is an instance of the cls, then it is returned
            * if obj is a Mapping (like `dict`), then it is passed to :meth:`cls.validate_dict`
            * if obj is a string, it is converted to stream-like and passed to :meth:`cls.validate_yaml`
            * if obj is a stream, it is passed to :meth:`cls.validate_yaml`

        Args:
            obj (obj, dict, str, stream): The various inputsIf an object is supplied,
            it is checked to
            be an instance of
            :class:`MicroBenthosModel`. If a dictionary is supplied then it is loaded with
            :meth:`validate_dict`. If a stream is supplied, it is considered to be a path to the
            model definition yaml file and is loaded with :meth:`validate_yaml`.

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

        elif isinstance(obj, basestring):
            definition = validate_yaml(
                io.StringIO(unicode(obj)), **kwargs)

        elif isinstance(obj, (io.IOBase, file)):
            # a file-like object
            definition = validate_yaml(obj, **kwargs)

        else:
            raise NotImplementedError('Unknown type {} to create {} from'.format(type(obj), cls))

        definition_ = copy.deepcopy(definition)
        inst = cls(**definition)
        inst.definition_ = definition_
        return inst
