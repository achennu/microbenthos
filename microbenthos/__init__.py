# -*- coding: utf-8 -*-
from __future__ import division, print_function

__author__ = """Arjun Chennu"""
__email__ = 'achennu@mpi-bremen.de'
__version__ = '0.13'

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())

import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

from .utils import *
from .core import *
from .model import *
from .dataview import *
from .exporters import *


def setup_console_logging(name = None, level = 20):
    import logging
    name = name or __name__
    logger = logging.getLogger(name)

    from .utils.log import ColorizingStreamHandler, CONSOLE_DEBUG_FORMATTER, CONSOLE_SHORT_FORMATTER
    handler = ColorizingStreamHandler()

    # fmt = '%(module)s:%(funcName)s:%(lineno)d:%(levelname)s :: %(message)s'
    # fmter = logging.Formatter(fmt=fmt)

    fmter = CONSOLE_DEBUG_FORMATTER if level < 20 else CONSOLE_SHORT_FORMATTER
    handler.setFormatter(fmter)
    handler.setLevel(level)

    logger.addHandler(handler)
    logger.info('Set up console logging: {} level={}'.format(name, logger.getEffectiveLevel()))

def add_console_logging(verbose, start_level = logging.ERROR):
    if verbose is None:
        return

    level = (start_level - int(verbose) * 10)
    level = min(level, logging.CRITICAL)
    level = max(level, logging.DEBUG)

    try:
        from logutils.colorize import ColorizingStreamHandler as StreamHandler
        StreamHandler.level_map[logging.DEBUG] = (None, 'black', False)
        StreamHandler.level_map[logging.INFO] = (None, 'blue', False)
    except:
        from logging import StreamHandler
    finally:
        sh = StreamHandler()
        sh.setLevel(level=level)
        logger.addHandler(sh)
        logger.debug(f'Set console logging to level {level}')

    return level
