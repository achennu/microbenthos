=====
Usage
=====

MicroBenthos can be used to define a `benthic`_ microbial system, with multiple interacting
entities, and study the spatial and temporal evolution of the entities.

The main user interface for using MicroBenthos is to define a model and simulation in a
structured text file. The text file is structured in a format called YAML, which is  a
human-editable machine-friendly format. It takes a few minutes to `learn yaml`_ for regular use.
The :ref:`tutorials` provide guidance on defining and solving models of microbenthic systems. For
details on the concept and mechanisms behind the software, head over to the :ref:`design` section
. For details on the commands available in MicroBenthos, see :ref:`commands`.

.. _benthic: https://en.wikipedia.org/wiki/Benthos
.. _learn yaml: https://learnxinyminutes.com/docs/yaml/

.. toctree::
    :maxdepth: 2

    cli
    tutorials/tutorials

Running simulations
===================

The main command to run a simulation is ``microbenthos simulate``. A few main cases are described here below,
but see :ref:`cmd_simulate` for detailed options.


The ``simulate`` command takes a definition file (such as ``definition_input.yml``) as its main
argument.

::

    microbenthos simulate definition_input.yml

When run without arguments, a default `model_data` exporter is added to the simulation run. This
would result in several files being created in the current working directory, one of them being a
HDF5 data file, typically named `simulation_data.h5`. Alongside the data file, various run time
information is written out: a log file, software versions, and the validated definition of model
and simulation that was created from the supplied `definition.yml` file.

.. note::

    The default name for the output definition file is `definition.yml`. So if your input file is
    called `definition.yml`, then it will get overwritten on running the command.

In order to see a mathematical representation of the equations being solved for the model
simulation, use the ``--show-eqns`` option::

    microbenthos simulate definition_input.yml --show-eqns


With visualization
-------------------

The model parameters can be visualized during the simulation by invoking a graphical exporter
using the ``--plot`` flag.

::

    microbenthos simulate definition_input.yml --plot


This opens up a window with graphical plots of the model domain, the microbial groups,
irradiance, rates of the various microbial and abiotic processes and the distribution of the
analytes being solved for. Additionally, to save a video of the simulation run, use the
``--video`` flag::

    microbenthos simulate definition_input.yml --video


To specify the output directory to be other than the current one, use the ``-o`` option::

    microbenthos simulate definition_input.yml -o simrun23


.. _resume:

Resume simulation
------------------

Previously run simulations can be resumed, by using the ``--resume`` flag. The flag takes
an integer parameter, which is the index along the time dimension from which to resume  .
This follows `python indexing`_ semantics. Briefly, 0 refers to the first time point, and 1, 2,
3, ... to the subsequent time points. -1 refers to the last saved time point, -2 to the one
before that, etc.

So, to resume from the last saved time point::

    microbenthos simulate definition_input.yml --resume -1

Or from 10 time points before::

    microbenthos simulate definition_input.yml --resume -10

Or to start from the 100th time point::

    microbenthos simulate definition_input.yml --resume 100

Note that a supplied ``--resume`` directive takes precedence over ``--overwrite``. Also, that
``--resume 0`` is equivalent to ``--overwrite``.


.. _python indexing: https://docs.python.org/2.7/library/stdtypes.html#sequence-types-str-unicode-list-tuple-bytearray-buffer-xrange

Render video from simulation
------------------------------

To create an animated visualization from a saved model data file, use the ``export video`` command::

    microbenthos export video simulation_data.h5 --show

The ``--show`` option creates the current frame being rendered to also be shown on the screen.
See :ref:`cmd_video` for details. Note that some :mod:`matplotlib` backends (such as Tk) may show
the canvas on the screen anyway.


