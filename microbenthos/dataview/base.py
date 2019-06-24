import abc
import logging

from fipy import PhysicalField
from fipy.tools import numerix as np


class ModelData(object, metaclass=abc.ABCMeta):
    """
    Abstract Base Class that encapsulates the model data from a simulation, and provides a uniform
    interface to access elements in the nested hierarchy.
    """

    PATH_DEPTHS = '/domain/depths'
    PATH_TIMES = '/time'
    ENTRY_ENV = 'env'
    ENTRY_EQUATIONS = 'equations'
    ENTRY_MICROBES = 'microbes'
    ENTRY_MICROBE_FEATURES = 'features'
    ENTRY_IRRADIANCE = 'irradiance'
    PATH_IRRADIANCE_CHANNELS = '/'.join([
        ENTRY_ENV,
        ENTRY_IRRADIANCE,
        'channels'
        ])

    def __init__(self, store = None):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('{} initialized'.format(self.__class__.__name__))

        #: the root data store
        self._store = None
        #: numerical array of the model clock times
        self.times = None
        #: numerical array of the domain depths
        self.depths = None
        #: Set of data paths for equation variables
        self.eqn_vars = set()
        #: Set of data paths for equation process expressions
        self.eqn_processes = set()
        #: Set of data paths for equation source totals
        self.eqn_source_totals = set()
        #: Set of data paths for equation var actual density
        self.eqn_var_actual = set()
        #: Set of data paths for equation var expected density
        self.eqn_var_expected = set()
        #: Set of data paths var (expected - actual)
        self.eqn_var_difference = set()
        #: set of data paths for microbial features
        self.microbe_features = set()
        #: set of data paths for irradiance intensity channels
        self.irradiance_intensities = set()
        #: mapping of aliased to real path
        self.aliased_paths = dict()
        #: mapping of derived paths to its inputs and processor
        self.derived_paths = dict()

        self.tdim = 0

        if store is not None:
            self.store = store

    @property
    def store(self):
        """
        The backing data store
        """
        return self._store

    @store.setter
    def store(self, obj):
        if self.check_store(obj):
            self._store = obj
            self.update()
        else:
            raise ValueError('Store type {} not valid!'.format(type(obj)))

    def get_data(self, path, tidx = None):
        """
        Get the data at the given path and time index

        The path is first checked if it is in the :attr:`aliased_paths` or :attr:`derived_paths`,
        and if not the data is looked for in the store.

        Args:
            path (str): A dotted path to the data
            tidx (int): The index for the :attr:`.times`

        Returns:
            A :class:`PhysicalField` of the data

        """
        self.logger.debug('Getting data from {} at time index {}'.format(path, tidx))

        if path in self.aliased_paths:
            path = self.aliased_paths[path]

        if path in self.derived_paths:
            self.logger.debug('Processing derived path: {}'.format(path))
            input_names, processor = self.derived_paths[path]
            inputs = [self.read_data_from(p, tidx) for p in input_names]
            data = processor(*inputs)
            self.logger.debug('Calculated derived data: {} {}'.format(data.shape, data.unit))
            return data

        else:
            return self.read_data_from(path, tidx)

    @abc.abstractmethod
    def check_store(self, obj):
        """
        Check if the given store is of the right type

        Returns:
            bool: True if a valid store obj
        """

    @abc.abstractmethod
    def get_node(self, path):
        """
        Return the node at the given path

        Args:
            path (str): A "/" separated path

        Returns:
            The node in the nested data store

        Raises:
            KeyError: if no such node exists
        """

    @abc.abstractmethod
    def read_data_from(self, path, tidx):
        """
        Data read out method to be implemented by subclasses

        Returns:
            a :class:`PhysicalField` of the data
        """

    @abc.abstractmethod
    def read_metadata_from(self, path):
        """
        Reads out the metadata for a given node in the model data

        Returns:
            a :class:`dict` of the metadata

        """

    def update(self):
        if self.store is None:
            raise RuntimeError('Model data store is empty!')

        self.update_domain_info()
        self.update_equations()
        self.update_microbes()
        self.update_irradiance()
        self.logger.info('Updated model dataview')

    def update_domain_info(self):
        """
        Read in the domain info and create the attributes :attr:`.times` and :attr:`.depths`.

        """

        self.depths = self.read_data_from(self.PATH_DEPTHS)
        self.logger.debug('Domain depths ({}): {}--> {}'.format(
            self.depths.shape,
            self.depths[0],
            self.depths[1],
            ))

        self.times = self.read_data_from(self.PATH_TIMES)
        self.logger.debug(
            'Times ({}): {} --> {}'.format(
                self.times.shape,
                self.times[0],
                self.times[-1],
                ))

    def update_equations(self):
        """
        Update the information about the equation variables and sources in :attr:`.eqn_vars`,
        :attr:`.eqn_source_totals` and :attr:`.eqn_processes`.
        """
        self.logger.debug('Updating equations')
        eqn_sources = set()
        eqn_vars = set()
        eqn_source_totals = set()
        eqn_var_actual = set()
        eqn_var_expected = set()
        eqn_var_difference = set()

        eqns = self.store[self.ENTRY_EQUATIONS]
        for eqnname in eqns:
            self.logger.debug('Collecting equation vars & sources for {}'.format(eqnname))

            transient = self.read_metadata_from('/'.join([
                self.ENTRY_EQUATIONS,
                eqnname,
                'transient'
                ]))
            varname = tuple(transient.keys())[0]
            varname = varname.replace('domain', 'env').replace('.', '/')
            eqn_vars.add(varname)

            sources_path = '/'.join([
                self.ENTRY_EQUATIONS,
                eqnname,
                'sources',
                ])
            aliased_sources_path = varname + '/sources_total'
            self.add_aliased_path(sources_path, aliased_sources_path)

            eqn_source_totals.add(aliased_sources_path)

            sources = self.read_metadata_from(sources_path).keys()

            self.logger.debug('Eqn {} with sources: {}'.format(varname, sources))
            for sname in sources:
                eqn_sources.add(sname.replace('.', '/'))

            tracked_path = '/'.join([
                self.ENTRY_EQUATIONS,
                eqnname,
                'tracked_budget'
                ])
            actual = tracked_path + '/var_actual'
            actual_alias = varname + '/actual'
            if actual_alias not in self.aliased_paths:
                self.add_aliased_path(actual, actual_alias)

            expected = tracked_path + '/var_expected'
            expected_alias = varname + '/expected'
            if expected_alias not in self.aliased_paths:
                self.add_aliased_path(expected, expected_alias)

            eqn_var_actual.add(actual_alias)
            eqn_var_expected.add(expected_alias)

            difference = varname + '/difference'

            def relative_error(a, b):
                if np.allclose(b.numericValue, 0):
                    return PhysicalField(0.0, '')
                else:
                    return PhysicalField((a - b) / a, '')

            if difference not in self.derived_paths:
                self.add_derived_data(difference,
                                      inputs=(expected, actual),
                                      processor=relative_error
                                      )
            eqn_var_difference.add(difference)

        self.eqn_vars = eqn_vars
        self.eqn_processes = eqn_sources
        self.eqn_source_totals = eqn_source_totals
        self.eqn_var_actual = eqn_var_actual
        self.eqn_var_expected = eqn_var_expected
        self.eqn_var_difference = eqn_var_difference

        self.logger.debug('Updated equation vars: {}'.format(self.eqn_vars))
        self.logger.debug('Updated equation sources: {}'.format(self.eqn_processes))

    def add_aliased_path(self, path, alias):
        """
        Alias a given path
        """
        self.logger.debug('Aliasing path {} --> {}'.format(path, alias))

        try:
            node = self.get_node(alias)
        except KeyError:
            node = None
        finally:
            if node is not None:
                raise ValueError('Aliased path exists in store! {!r}'.format(alias))

        self.aliased_paths[alias] = path

    def add_derived_data(self, path, inputs, processor):
        """
        Add a path entry for derived data

        This method is used to add a data path which will provide data based on the `inputs` and
        a callable `processor`, as `processor(*inputs)`.

        Args:
            path (str): The new derived path
            inputs (tuple): Set of input paths for the calculation
            processor (callable): The callable that performs the calculation

        Returns:
            PhysicalField: The output from the calculation

        Raises:
            ValueError: if `path` exists in store
            TypeError: if `processor` is not a callable
        """
        self.logger.debug('Adding derived path: {}'.format(path))

        try:
            node = self.get_node(path)
        except KeyError:
            node = None
        finally:
            if node is not None:
                raise ValueError('Derived path exists in store! {!r}'.format(path))

        if not callable(processor):
            raise TypeError('Given data processor is not a callable: {}'.format(processor))

        assert isinstance(inputs, (tuple, list))

        if path in self.derived_paths:
            self.logger.warning('Derived path exists and will be overwritten: {!r}'.format(path))

        self.derived_paths[str(path)] = (inputs, processor)
        self.logger.debug('Added derived path: {}'.format(path))

    def update_tracked(self):
        """
        Update the information about the tracked history of the equation variables & sources
        """

    def update_microbes(self):
        """
        Update the microbial features from the model data into :attr:`.microbes_features`
        """
        self.logger.debug('Updating microbial features')
        microbes_features = set()

        for mname in self.store[self.ENTRY_MICROBES]:
            microbe = self.store[self.ENTRY_MICROBES][mname]

            for fname in microbe[self.ENTRY_MICROBE_FEATURES]:
                feature = microbe[self.ENTRY_MICROBE_FEATURES][fname]
                self.logger.debug('Updating info on microbe feature {}.{}'.format(
                    mname, fname
                    ))
                data_path = '/'.join([
                    self.ENTRY_MICROBES,
                    mname,
                    self.ENTRY_MICROBE_FEATURES,
                    fname,
                    ])
                microbes_features.add(data_path)

        self.microbe_features = microbes_features
        self.logger.debug('Updated microbial features: {}'.format(self.microbe_features))

    def update_irradiance(self):
        """
        Update the set of data paths for irradiance intensities in :attr:`.irradiance_intensities`.
        """
        self.logger.debug('Updating irradiances')
        irradiances = set()

        irradiance = self.store[self.ENTRY_ENV].get(self.ENTRY_IRRADIANCE)
        if not irradiance:
            self.logger.debug('No irradiance info found')

        else:

            # load irradiance cycle info
            linfo = dict(irradiance.attrs)
            self.diel_period = PhysicalField(linfo['hours_total'])
            self.diel_zenith = PhysicalField(linfo['zenith_time'])

            for chname in irradiance['channels']:
                data_path = self.PATH_IRRADIANCE_CHANNELS + '/'.join([
                    '',  # for a leading slash in the subpath
                    chname,
                    'intensity'
                    ])
                irradiances.add(data_path)
                self.logger.debug('Added irradiance intensity: {}'.format(data_path))

        self.irradiance_intensities = irradiances
        self.logger.debug('Updated irradiance intensities: {}'.format(self.irradiance_intensities))
