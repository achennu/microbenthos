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
