.. _commands:

Commands
=========

MicroBenthos provides a command line interface for its operations under ``microbenthos``.

.. program-output:: microbenthos

To view the log messages on the console, use the ``-v`` flag. For increased verbosity of console
log messages, use it multiple times, e.g. ``-vv``, ``-vvv``, etc.

The various subcommands available are:

.. _cmd_simulate:

Command: simulate
------------------

.. command-output:: microbenthos simulate --help

.. note::

    By default, a progress bar exporter and model data exporter are added if not specified. The
    progress bar can be turned off using the ``--no-progress`` switch.

.. _cmd_video:

Command: export video
----------------------

.. command-output:: microbenthos export video --help

.. note::

    The graphical exporter in MicroBenthos uses :mod:`matplotlib` to render the plots and
    animations. For video export, ``ffmpeg`` or one of the other animation backends for
    :mod:`matplotlib.animation` should be available.

Command: export model
----------------------

.. command-output:: microbenthos export model --help

Command: setup completion
--------------------------

.. command-output:: microbenthos setup completion --help
