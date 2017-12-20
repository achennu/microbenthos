# -*- coding: utf-8 -*-

__author__ = """Arjun Chennu"""
__email__ = 'achennu@mpi-bremen.de'
__version__ = '0.1.0'

# TODO: refactor logging so that config doesn't occur at import level

from .domain import SedimentDBLDomain
from .entity import Entity, DomainEntity, Variable
from .process import Process, ExprProcess
from .microbes import MicrobialGroup
from .loader import from_yaml


def setup_console_logging(name=None, level=20):
    import logging
    name = name or __name__
    logger = logging.getLogger(name)
    logger.setLevel(level)

    from .utils.log import ColorizingStreamHandler
    handler = ColorizingStreamHandler()

    fmt = '%(module)s:%(funcName)s:%(levelname)s :: %(message)s'
    fmter = logging.Formatter(fmt=fmt)
    handler.setFormatter(fmter)

    logger.addHandler(handler)
    logger.info('Set up console logging: {} level={}'.format(name, logger.getEffectiveLevel()))
