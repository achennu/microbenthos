import io
import logging
from collections import Mapping

from .loader import from_yaml, from_dict


class CreateMixin(object):
    @classmethod
    def create_from(cls, obj, **kwargs):
        """
        Instantiate class from the given object

        Various types of `obj` are handled:
            * if obj is an instance of the cls, then it is returned
            * if obj is a Mapping (like `dict`), then it is passed to :meth:`cls.from_dict`
            * if obj is a string, it is converted to stream-like and passed to :meth:`cls.from_yaml`
            * if obj is a stream, it is passed to :meth:`cls.from_yaml`

        Args:
            obj (obj, dict, str, stream): The various inputsIf an object is supplied,
            it is checked to
            be an instance of
            :class:`MicroBenthosModel`. If a dictionary is supplied then it is loaded with
            :meth:`from_dict`. If a stream is supplied, it is considered to be a path to the
            model definition yaml file and is loaded with :meth:`from_yaml`.

        """
        logger = logging.getLogger(__name__)
        logger.debug('Creating instance of {} from {}'.format(cls, type(obj)))

        if isinstance(obj, cls):
            obj.definition_ = None
            return obj

        elif isinstance(obj, Mapping):
            inst = cls.from_dict(obj)
            inst.definition_ = obj
            return inst

        elif isinstance(obj, basestring):
            inst = cls.from_yaml(io.StringIO(unicode(obj)))
            inst.definition_ = obj
            return inst

        elif isinstance(obj, io.IOBase):
            # a file-like object
            inst = cls.from_yaml(obj, **kwargs)
            obj.seek(0)
            inst.definition_ = obj.readlines()
            return inst

        else:
            raise NotImplementedError('Unknown type {} to create {} from'.format(type(obj), cls))

    @classmethod
    def from_yaml(cls, stream, **kwargs):
        """
        Create an instance from a YAML format text stream. See
        :meth:`from_yaml` for arguments.

        Args:
            stream (file-like stream): Input stream for yaml, which will be validated with the
            internal or supplied schema

        Returns:
            the created instance

        """
        if kwargs.get('schema_stream') is None:
            if kwargs.get('key') is None:
                kwargs['key'] = cls.schema_key
        return cls(**from_yaml(stream, **kwargs))

    @classmethod
    def from_dict(cls, mdict, **kwargs):
        """
        Create an instance from a dictionary. See :meth:`from_dict` for arguments.

        Args:
            mdict (dict): Definition dicitonary which will be validated with internal or supplied
            schema

        Returns:
            The created instance

        """
        if kwargs.get('schema_stream') is None:
            if kwargs.get('key') is None:
                kwargs['key'] = cls.schema_key
        inst = cls(**from_dict(mdict, **kwargs))
        return inst
