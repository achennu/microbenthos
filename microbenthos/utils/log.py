import logging
from logutils.colorize import ColorizingStreamHandler

level_map = {
    logging.DEBUG: (None, 'blue', False),
    logging.INFO: (None, 'cyan', False),
    logging.WARNING: (None, 'yellow', False),
    logging.ERROR: (None, 'red', False),
    logging.CRITICAL: ('red', 'white', True),
}
ColorizingStreamHandler.level_map = level_map

CONSOLE_DEBUG_FORMATTER = logging.Formatter('%(module)-20s: %(filename)15s:%(lineno)-3d : %(levelname)-8s \t %(message)s',  '%H:%M:%S')
CONSOLE_SHORT_FORMATTER = logging.Formatter('%(message)s',  '%H:%M:%S')

SIMULATION_DEFAULT_FORMATTER = logging.Formatter('%(message)s ::: %(asctime)s')
SIMULATION_DEBUG_FORMATTER = logging.Formatter('%(message)s ::: %(asctime)s || %(name)s:%(lineno)-3d ::')

