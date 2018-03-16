import contextlib
import importlib
import logging
import os
import warnings
from collections import OrderedDict

import click

from ..exporters import BaseExporter
from ..model import MicroBenthosModel, Simulation
from ..utils import yaml, find_subclasses_recursive
from ..utils.log import SIMULATION_DEFAULT_FORMATTER, SIMULATION_DEBUG_FORMATTER

DUMP_KWARGS = dict(
    indent=4,
    explicit_start=True,
    explicit_end=True,
    default_flow_style=False
    )


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
        * run the simulation evolution
        * clean up
    """

    def __init__(self, output_dir = None,
                 resume = None,
                 confirm = False,
                 compression = 6,
                 overwrite=False,
                 model = None,
                 simulation = None,
                 progress = False,
                 plot = False,
                 video = False,
                 frames = False,
                 budget = False,
                 exporters = (),
                 show_eqns = False,
                 ):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Initializing {}'.format(self))

        self._model = None
        self._simulation = None
        self.exporters = OrderedDict()

        self.output_dir = output_dir
        self._log_fh = None

        if resume == 0:
            click.secho(
                'Resume = 0 implies to restart simulation. Setting overwrite=True instead',
                fg='yellow')
            resume = None
            overwrite = True

        self.resume = resume
        self.overwrite = overwrite
        self.confirm = confirm

        self._check_data_path()

        # load up exporters
        from microbenthos.utils import find_subclasses_recursive
        from microbenthos.exporters import BaseExporter

        self._exporter_classes = {e._exports_: e for e in
                                  find_subclasses_recursive(BaseExporter)}

        if model:
            self.model = model

        if simulation:
            self.simulation = simulation

        self.resume_existing_simulation()

        # add data exporter by default
        self.add_exporter('model_data',
                          compression=compression,
                          overwrite=self.overwrite)

        if progress:
            self.add_exporter('progress')

        if plot or video or frames:
            self.add_exporter('graphic',
                              write_video=video,
                              show=plot,
                              track_budget=budget,
                              write_frames=frames)

            if self.resume and video:
                click.secho('Video will begin from this simulation run, since resume is set!',
                            fg='yellow')

        # add other exporters
        for name, exptype in exporters:
            self.add_exporter(exptype=exptype, name=name)

        if show_eqns:
            click.secho('Solving the equation(s):', fg='green')
            for neqn, eqn in self.model.equations.items():
                click.secho(eqn.as_pretty_string(), fg='green')

        click.secho(
            'Simulation setup: solver={0.fipy_solver} '
            'max_sweeps={0.max_sweeps} max_residual={0.residual_target} '
            'timestep_lims=({1}, {2})'.format(
                self.simulation, *self.simulation.simtime_lims),
            fg='yellow')
        click.secho('Simulation clock at {}. Run till {}'.format(self.model.clock,
                                                                 self.simulation.simtime_total),
                    fg='yellow')

    def __repr__(self):
        return 'SimulationRunner'

    @property
    def data_outpath(self):
        return os.path.join(self.output_dir, 'simulation_data.h5')

    def _check_data_path(self):
        # both overwrite and resume cannot be true by the user
        if os.path.exists(self.data_outpath):
            if self.overwrite and self.resume is not None:
                click.secho('Both overwrite and resume cannot be set', fg='red')
                raise click.Abort()

            if not self.confirm and (not self.resume) and (not self.overwrite):
                click.secho(
                    'Ambiguous case with --no-confirm: file exists and neither --overwrite nor'
                    ' --resume were specified',
                    fg='red')
                raise click.Abort()

            else:
                if self.resume:
                    self.overwrite = False
                else:
                    if self.confirm:
                        click.confirm(
                            'Overwrite existing file: {}?'.format(self.data_outpath),
                            abort=True)
                    self.overwrite = True
                    click.secho('Deleting output path: {}'.format(self.data_outpath), fg='red')
                    os.remove(self.data_outpath)

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
            raise ValueError('No exporter of type {!r} found. Available: {}'.format(
                exptype, self._exporter_classes.keys()))

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

    def resume_existing_simulation(self):
        if self.resume is None:
            self.logger.debug(
                'resume={}, so will not resume from existing file'.format(self.resume))
            return

        from fipy import PhysicalField

        # open the store and read out the time info
        with hdf.File(self.data_outpath, 'r') as store:
            tds = store['/time/data']
            nt = len(tds)
            target_time = tds[self.resume]
            latest_time = tds[-1]
            time_unit = tds.attrs['unit']

        target_time = PhysicalField(target_time, time_unit)
        latest_time = PhysicalField(latest_time, time_unit)

        click.secho(
            '\n\nModel resume set: rewind from latest {} ({}) to {} ({})?'.format(
                latest_time, nt,
                target_time, self.resume
                ), fg='red')

        if self.confirm:
            click.confirm('Rewinding model clock can lead to data loss! Continue?',
                          default=False, abort=True)

        try:
            with hdf.File(self.data_outpath, 'a') as store:
                self.model.restore_from(store, time_idx=self.resume)
            click.secho('Model restore successful. Clock = {}\n\n'.format(self.model.clock),
                        fg='green')
            self.simulation.simtime_step = 1
            # set a small simtime to start
        except:
            click.secho('Simulation could not be restored from given data file!', fg='red')
            raise  # click.Abort()

    def setup_logfile(self, mode = 'a'):
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
                ), fp, **DUMP_KWARGS)

    def save_run_info(self):
        """
        Save the runner info to output_dir
        """

        self.logger.info('Saving runner info: runner.yml')
        with open(os.path.join(self.output_dir, 'runner.yml'), 'w') as fp:
            yaml.dump(self.get_info(), fp, **DUMP_KWARGS)

    def get_info(self):
        """
        Return a dictionary of info about the runtime environment
        """
        runner = dict(cls=self.__class__.__name__)
        libraries = ['fipy', 'scipy', 'PyTrilinos', 'pysparse', 'numpy', 'cerberus', 'yaml',
                     'sympy', 'click', 'h5py', 'matplotlib', 'microbenthos']
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
        state = self.simulation.get_state(state=self.model.snapshot())

        for expname, exporter in self.exporters.items():
            try:
                exporter.setup(self, state)
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
        if self.confirm:
            click.confirm('Proceed with simulation run?',
                          default=True, abort=True)

        click.secho('Starting simulation...', fg='green')

        self.logger.debug('Preparing to run simulation')

        self.check_simulation()

        if not self.exporters:
            self.logger.warning('No exporters set for simulation run!')

        self._create_output_dir()

        self.setup_logfile()

        self.save_definitions()

        self.save_run_info()

        self.prepare_simulation()

        self.logger.info('Solving equations')
        for name, eqn in self.model.equations.items():
            self.logger.info(eqn.as_pretty_string())

        self.logger.info('As fipy equations')
        for name, eqn in self.model.equations.items():
            self.logger.info('Equation {}: {!r}'.format(name, eqn.obj))

        warnings.filterwarnings('ignore', category=RuntimeWarning, module='fipy')

        with self.exporters_activated():
            for step in self.simulation.evolution():
                try:
                    # time.sleep(1e-5)
                    # step is (num, state) is the model snapshot
                    if step:
                        num, state = step

                        export_due = self.simulation.export_due() or (num == 0)
                        self.logger.info('Step #{}: Exporting model state'.format(num))

                        for exporter in self.exporters.values():
                            if export_due:
                                exporter.process(num, state)
                            else:
                                if exporter.is_eager:
                                    exporter.process(num, state)

                        self.logger.info('Step #{}: Export done'.format(num))
                    else:
                        self.logger.warning('Empty model state received!')

                except KeyboardInterrupt:
                    self.logger.error("Keyboard interrupt on simulation run!")
                    break

        self.teardown_logfile()
        warnings.resetwarnings()

        click.secho('Simulation done.', fg='green')
