.. highlight:: shell

.. _installation:

============
Installation
============

Dependencies
-------------

The dependencies for :mod:`microbenthos` are:

* python3
* numpy
* scipy
* fipy
* sympy
* cerberus
* click
* pyyaml
* h5py (and libhdf)
* tqdm
* matplotlib >=2.1
* logutils

Install
------------

Install MicroBenthos using either::

    pip install microbenthos

Or using::

    pip install git+https://github.com/achennu/microbenthos


Source install
--------------

The sources for MicroBenthos can be downloaded from the `github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/achennu/microbenthos

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/achennu/microbenthos/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ # If using conda...
    $ conda env create -n microbenthos -f microbenthos/requirements.yml
    $ conda env activate microbenthos
    $ cd microbenthos
    $ python setup.py install


.. _github repo: https://github.com/achennu/microbenthos
.. _tarball: https://github.com/achennu/microbenthos/tarball/master


.. _devinstall:

Development install
--------------------

MicroBenthos uses :mod:`pytest` to run automated unit testing. If you want to
run the included tests, then install the test requirements::

    $ pip install microbenthos[test]

To run the tests, change to the tests directory of the source tree.

.. code-block:: shell

    $ cd microbenthos/tests
    $ pytest .

MicroBenthos currently includes 250+ tests of its API entities.

MicroBenthos documentation is rendered using :mod:`sphinx`. To generate the
documentation from the source tree, install the docs requirements and then run
the build command.

.. code-block:: shell

    $ pip install microbenthos[docs]

    $ # change to the docs directory of microbenthos
    $ cd microbenthos/docs
    $ make html
