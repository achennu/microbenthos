import contextlib
import importlib
import logging
import os
from collections import OrderedDict

from ..exporters import BaseExporter
from ..model import MicroBenthosModel, Simulation
from ..utils import yaml, find_subclasses_recursive
from ..utils.log import SIMULATION_DEFAULT_FORMATTER, SIMULATION_DEBUG_FORMATTER

"""
def run():
    model = MicroBenthosModel.from_yaml(model_file)
    sim = Simulation.from_yaml(sim_file)
    sim.model = model
    sim.start()

    data_file = 'abc.h5'
    start_logfile()
    save_model_file()
    save_simulation_file(with_software_versions=True)

    for step in sim.stepper:
        sim.run_timestep()
        snap = sim.model.snapshot()
        save_snapshot(data_file, snap)

        for exporter in exporters:
            exporter.process(snap)
"""


class SimulationRunner(object):
    """
    Class that handles the pipeline of creating and running simulations of models, and generating
    outputs from it.

    This class will:

        * check that the model & simulation setup are complete
        * check the output path
        * create a log file
        * export the model definition
        * export the run setup
        * setup the exporters
        * run the simulation
        * clean up
    """

    def __init__(self, output_dir = None, model = None, simulation = None):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Initializing {}'.format(self))

        self._model = None
        self._simulation = None
        self._exporter_classes = None
        self.exporters = OrderedDict()

        self.output_dir = output_dir
        self._log_fh = None

        if model:
            self.model = model

        if simulation:
            self.simulation = simulation

    def __repr__(self):
        return 'SimulationRunner'

    @property
    def model(self):
        """
        The model to run with the :attr:`simulation`. Typically an instance of
        :class:`~microbenthos.MicroBenthosModel`.
        """
        return self._model

    @model.setter
    def model(self, obj):
        if self.model is None:
            m = MicroBenthosModel.create_from(obj)
            self.logger.debug('Created model {}'.format(m))
            self._model = m
            self.logger.debug('Model set: {}'.format(self.model))
        else:
            raise RuntimeError('Model already set in runner!')

    @property
    def simulation(self):
        """
        The :class:`~microbenthos.Simulation` instance that will run with the :attr:`.model`
        """
        return self._simulation

    @simulation.setter
    def simulation(self, obj):
        if self.simulation is None:
            self._simulation = Simulation.create_from(obj)
            self.logger.debug('Simulation set: {}'.format(self.simulation))
            if self.model:
                self.simulation.model = self.model
        else:
            raise RuntimeError('Simulation already set in runner!')

    def _load_exporters(self):
        self._exporter_classes = {c._exports_: c for c in find_subclasses_recursive(BaseExporter)}
        self.logger.debug("Loaded exporter classes: {}".format(self._exporter_classes.keys()))

    def add_exporter(self, exptype, name = None, **kwargs):
        """
        Add an exporter to the simulation run

        Args:
            obj: Object to create instance from. See :attr:`BaseExporter.create_from`
            name (str): The name to set for the exporter. If None, then the
            :attr:`BaseExporter._exports_` is used.

        Returns:
            The name of the exporter created
        """
        self.logger.debug('Adding exporter for {}'.format(exptype))
        if not name:
            name = exptype

        if name in self.exporters:
            raise ValueError('Exporter with name {!r} already exists!')

        if not self._exporter_classes:
            self._load_exporters()

        cls = self._exporter_classes.get(exptype)
        if cls is None:
            raise ValueError('No exporter of type {!r} found. Available: {}'.format(exptype,
                                                                                    self._exporter_classes.keys()))

        instance = cls(name=name, **kwargs)
        self.logger.info('Adding exporter {!r}: {!r}'.format(name, instance))
        self.exporters[name] = instance

    def _create_output_dir(self):

        if self.output_dir is None:
            raise ValueError('output_dir cannot be empty for creation')

        if not os.path.isdir(self.output_dir):
            self.logger.debug('Creating output directory')
            try:
                os.makedirs(self.output_dir)
            except OSError:
                self.logger.error('Error creating output_dir')
                raise

    def setup_logfile(self, mode = 'w'):
        """
        Setup log file in the output directory
        """
        logfile = os.path.join(self.output_dir, 'simulation.log')
        logger = logging.getLogger(__name__.split('.')[0])
        lvl = 20

        fh = self._log_fh = logging.FileHandler(logfile, mode=mode)
        fh.setLevel(lvl)

        fmt = SIMULATION_DEBUG_FORMATTER if lvl < 20 else SIMULATION_DEFAULT_FORMATTER
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        self.logger.debug('Created simulation logfile: {}'.format(logfile))

    def teardown_logfile(self):
        self.logger.debug('Ending simulation logfile!')
        logger = logging.getLogger(__name__.split('.')[0])
        logger.removeHandler(self._log_fh)

    def save_definitions(self):
        """
        Save the model and simulation definition to the output directory
        """
        self.logger.info('Saving model definition: model.yml')
        with open(os.path.join(self.output_dir, 'model.yml'), 'w') as fp:
            yaml.dump(dict(
                model=self.model.definition_,
                simulation=self.simulation.definition_
                ), fp)

    def save_run_info(self):
        """
        Save the runner info to output_dir
        """

        self.logger.info('Saving runner info: runner.yml')
        with open(os.path.join(self.output_dir, 'runner.yml'), 'w') as fp:
            yaml.dump(self.get_info(), fp)

    def get_info(self):
        """
        Return a dictionary of info about the runtime environment
        """
        runner = dict(cls=self.__class__.__name__)
        libraries = ['fipy', 'scipy', 'PyTrilinos', 'pysparse', 'numpy', 'cerberus', 'yaml',
                     'sympy', 'click', 'h5py', 'matplotlib']
        library_versions = {}
        for name in libraries:
            try:
                lib = importlib.import_module(name)
                version = lib.__version__
                library_versions[name] = version
            except ImportError:
                self.logger.debug('Could not import module: {}'.format(name))

        exporters = {}
        for expname in self.exporters:
            exp = self.exporters[expname]
            exporters[expname] = exp.get_info()

        return dict(libraries=library_versions, exporters=exporters, runner=runner)

    def check_simulation(self):
        self.logger.info('Checking simulation')
        required = [self.model, self.simulation]
        if not all([s is not None for s in required]):
            self.logger.error('Setup incomplete: {}'.format(required))

            raise RuntimeError(
                'Simulation run cannot begin without model and simulation')

    def prepare_simulation(self):
        """
        Prepare the simulation by setting up the model
        """
        self.logger.info('Preparing simulation')
        if not self.simulation.model:
            if self.model:
                self.simulation.model = self.model

    @contextlib.contextmanager
    def exporters_activated(self):
        """
        A context manager that starts and closes the exporters
        Returns:
        """
        self.logger.info('Preparing exporters: {}'.format(self.exporters.keys()))
        for expname, exporter in self.exporters.items():
            try:
                exporter.setup(self)
            except:
                self.logger.error('Error in setting up exporter: {}'.format(expname))
                raise

        yield

        # once context returns
        self.logger.info('Closing exporters: {}'.format(self.exporters.keys()))
        for expname, exporter in self.exporters.items():
            if exporter.started:
                try:
                    exporter.close()
                except:
                    self.logger.error('Error in closing exporter: {}'.format(expname))
                    raise

    def run(self):
        """
        Run the simulation run with the stored model and simulation setup. There needs to be
        at least one exporter (typically a data exporter)


        Returns:

        """
        self.logger.debug('Preparing to run simulation')

        self.check_simulation()

        if not self.exporters:
            self.logger.warning('No exporters set for simulation run!')

        self._create_output_dir()

        self.setup_logfile()

        self.save_definitions()

        self.save_run_info()

        self.prepare_simulation()

        for name, eqn in self.model.equations.items():
            self.logger.info('Equation {}: {!r}'.format(name, eqn.obj))

        with self.exporters_activated():
            for step in self.simulation.evolution():
                try:
                    # step is (num, state) is the model snapshot
                    if step:
                        num, state = step

                        self.logger.info('Step #{}: Exporting model state'.format(num))
                        for exporter in self.exporters.values():
                            exporter.process(num, state)

                        self.logger.info('Step #{}: Export done'.format(num))
                    else:
                        self.logger.debug('Step #{}: Empty model state received!'.format(num))

                except KeyboardInterrupt:
                    self.logger.error("Keyboard interrupt on simulation run!")
                    break

        self.teardown_logfile()
