.. highlight:: shell

.. _installation:

============
Installation
============

Dependencies
-------------

The dependencies for :mod:`microbenthos` are:

* python 2.7
* numpy
* scipy >= 1.0
* fipy >3.1.3
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

MicroBenthos runs on python 2.7. The code base is written to be python 2 and 3 compatible, but
since a primary dependency (:mod:`fipy`) has yet to be ported to python3, you should install
MicroBenthos into a python2 environment.

Additionally, due to `fixed bugs <https://github.com/usnistgov/fipy/issues/534>`_ not yet
included in an official release, please install fipy from the repository.

If using the `conda` package manager, then create a virtual environment using::

    conda create -n microbenthos -c anaconda python=2.7 numpy scipy pyyaml h5py matplotlib

If you are using another python environment manager, like virtualenv, then installation of these
packages with C extensions can be performed as usual.

In the ``microbenthos`` environment, install fipy from the git repo::

    source activate microbenthos
    pip install git+https://github.com/usnistgov/fipy

Once :mod:`fipy` greater than v3.1.3 is released, then installation can be performed with::

    pip install fipy

Now install MicroBenthos using either::

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

    $ python setup.py install


.. _github repo: https://github.com/achennu/microbenthos
.. _tarball: https://github.com/achennu/microbenthos/tarball/master


.. _devinstall:

Development install
--------------------

MicroBenthos uses :mod:`pytest` to run automated unit testing. If you want to run the included
tests, then install the test requirements::

    $ pip install microbenthos[test]

To run the tests, change to the tests directory of the source tree.

.. code-block:: shell

    $ cd microbenthos/tests
    $ pytest .

MicroBenthos currently includes 250+ tests of its API entities.

MicroBenthos documentation is rendered using :mod:`sphinx`. To generate the documentation from
the source tree, install the docs requirements and then run the build command.

.. code-block:: shell

    $ pip install microbenthos[docs]

    $ # change to the docs directory of microbenthos
    $ cd microbenthos/docs
    $ make html
