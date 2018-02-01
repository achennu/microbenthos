# -*- coding: utf-8 -*-

__author__ = """Arjun Chennu"""
__email__ = 'achennu@mpi-bremen.de'
__version__ = '0.2.0'

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())

from .utils import *
from .core import *
from .model import *


def setup_console_logging(name=None, level=20):
    import logging
    name = name or __name__
    logger = logging.getLogger(name)

    from .utils.log import ColorizingStreamHandler
    handler = ColorizingStreamHandler()

    fmt = '%(module)s:%(funcName)s:%(levelname)s :: %(message)s'
    fmter = logging.Formatter(fmt=fmt)
    handler.setFormatter(fmter)
    handler.setLevel(level)

    logger.addHandler(handler)
    logger.info('Set up console logging: {} level={}'.format(name, logger.getEffectiveLevel()))
