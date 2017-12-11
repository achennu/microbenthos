import logging
from logutils.colorize import ColorizingStreamHandler

level_map = {
    logging.DEBUG: (None, 'cyan', False),
    logging.INFO: (None, 'blue', False),
    logging.WARNING: (None, 'yellow', False),
    logging.ERROR: (None, 'red', False),
    logging.CRITICAL: ('red', 'white', True),
}
ColorizingStreamHandler.level_map = level_map
