import abc
import logging


class ModelData(object):
    """
    Class that encapsulates the model data from a simulation run
    """

    __metaclass__ = abc.ABCMeta

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

        self._store = None
        #: the root data store
        self.times = None
        #: numerical array of the model clock times
        self.depths = None
        #: numerical array of the domain depths
        self.eqn_vars = set()
        #: Set of data paths for equation variables
        self.eqn_sources = set()
        #: Set of data paths for equation sources
        self.microbe_features = set()
        #: set of data paths for microbial features
        self.irradiance_intensities = set()
        #: set of data paths for irradiance intensity channels

        self.tdim = 0

        if store is not None:
            self.store = store

    @property
    def store(self):
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

        Args:
            path (str): A dotted path to the data
            tidx (int): The index for the :attr:`.times`

        Returns:
            A :class:`PhysicalField` of the data
        """
        self.logger.debug('Getting data from {} at time index {}'.format(path, tidx))
        return self.read_data_from(path, tidx)

    @abc.abstractmethod
    def check_store(self, obj):
        """
        Check if the given store is of the right type

        Returns:
            True if a valid store obj
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
        Read in the domain info and create the attributes :attr:`.times` and :attr:`depths`.

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
        Update the information about the equation variables and sources in :attr:`.eqn_vars` and
        :attr:`eqn_sources`.

        """
        self.logger.debug('Updating equations')
        eqn_sources = set()
        eqn_vars = set()

        eqns = self.store[self.ENTRY_EQUATIONS]
        for eqnname in eqns:
            self.logger.debug('Collecting equation vars & sources for {}'.format(eqnname))
            eqndef = eqns[eqnname]
            transient = self.read_metadata_from('/'.join([
                self.ENTRY_EQUATIONS,
                eqnname,
                'transient'
                ]))
            varname = transient.keys()[0]
            eqn_vars.add(varname.replace('domain', 'env').replace('.', '/'))

            sources = self.read_metadata_from('/'.join([
                self.ENTRY_EQUATIONS,
                eqnname,
                'sources'
                ])).keys()

            self.logger.debug('Eqn {} with sources: {}'.format(varname, sources))
            for sname in sources:
                eqn_sources.add(sname.replace('.', '/'))

        self.eqn_vars = eqn_vars
        self.eqn_sources = eqn_sources
        self.logger.debug('Updated equation vars: {}'.format(self.eqn_vars))
        self.logger.debug('Updated equation sources: {}'.format(self.eqn_sources))

    def update_microbes(self):
        """
        Update the microbial features from the model data into :attr:`microbes_features`
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
