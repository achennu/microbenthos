import logging

from microbenthos import DomainEntity, Process, Variable


class MicrobialGroup(DomainEntity):
    """
    Class to represent a category of micro-organisms, such as cyanobacteria, chemosynthetic
    sulfur bacteria, etc. This class is useful when the distribution of their biomass within the
    modelling domain needs to be specified and potentially modified over time, such as through
    growth or migration.
    """

    def __init__(self, name, features = None, processes = None, **kwargs):
        """
        Initialize a microbial group with a given name, and instantiate features and processes
        for the microbes..

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in MicrobialGroup')
        kwargs['logger'] = self.logger

        super(MicrobialGroup, self).__init__(**kwargs)

        self.name = str(name)
        self._biomass = None
        self.VARS = {}
        self.features = {}
        self.processes = {}

        if features:
            for fname, fdict in dict(features).items():
                self.add_feature_from(fname, **fdict)

        if processes:
            for pname, pdict in dict(processes).items():
                self.add_process_from(pname, **pdict)

        if self.biomass is None:
            self.logger.error('{} initialized but no biomass feature found!'.format(self))
            raise RuntimeError('{} needs feature "biomass"'.format(self))

        self.logger.debug('Initialized {}'.format(self))

    def __repr__(self):
        return '{}:Feat({}):Procs({})'.format(self.name, ','.join(self.features.keys()),
                                              ','.join(self.processes.keys()))

    def __getitem__(self, item):
        if item in self.features:
            return self.VARS[item]
        else:
            return self.domain[item]

    def __contains__(self, item):
        return (item in self.VARS) or (item in self.domain)

    def add_feature_from(self, name, **params):
        """
        Add a feature to the microbial group.

        This is used to define features such as biomass from a definition dictionary.

        Args:
            name (str): name of the feature
            **params: parameters to initialize the feature

        Returns:
            None
        """
        # feature variable should be stored here, not on domain
        if params['cls'].endswith('Variable'):
            params['init_params']['create']['store'] = False
            self.logger.debug('Set variable store = False')

        self.logger.debug('Dispatch init of feature {!r}: {}'.format(name, params))
        instance = self.from_dict(params)


        if name in self.features:
            self.logger.warning('Overwriting feature {!r} with {}'.format(name, instance))

        if isinstance(instance, Variable):
            self.VARS[instance.name] = instance.var

        self.logger.debug('{} added feature {}: {}'.format(self, name, instance))
        self.features[name] = instance

    def add_process_from(self, name, **params):
        """
        Add a process to the microbial group.

        This is used to define processes such as biomass growth or metabolism from a definition
        dictionary.

        Args:
            name (str): name of the process
            **params: parameters to initialize the feature

        Returns:
            None
        """
        self.logger.debug('Dispatch init of process {!r}'.format(name, params))
        instance = self.from_params(**params)
        assert isinstance(instance, Process), '{} not an instance of Process'

        if name in self.processes:
            self.logger.warning('Overwriting process {!r} with {}'.format(name, instance))

        self.logger.debug('{} added process {}: {}'.format(self, name, instance))
        self.processes[name] = instance

    @property
    def biomass(self):
        ret = self.features.get('biomass')
        if ret is None:
            self.logger.warning('Essential feature "biomass" of {} missing!'.format(self))
        return ret

    def on_domain_set(self):
        """
        Features, which are handlers for domain variables, receive the domain instances. However
        processes receive `self` as the domain, so that variable lookup happens first locally on
        the instance and then passed on to the domain.
        Returns:

        """

        for obj in self.features.values():
            self.logger.debug('Setting domain for {}'.format(obj))
            obj.domain = self.domain

        for obj in self.processes.values():
            self.logger.debug('Setting self as domain for {}'.format(obj))
            obj.domain = self

    def setup(self):
        """
        If the domain is available, then setup all the features and processes.

        """
        self.logger.debug('Setup of {}'.format(self))
        if self.check_domain():
            for obj in self.features.values() + self.processes.values():
                self.logger.debug('Setting up {}'.format(obj))
                obj.setup()
