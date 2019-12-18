import itertools
import logging

from . import DomainEntity, ModelVariable


class MicrobialGroup(DomainEntity):
    """
    Class to represent a category of microorganisms, such as cyanobacteria,
    sulfur bacteria, etc.

    This class defines the interface to

        * define :attr:`.features` such as :attr:`.biomass`, distributed
            through the domain
        * setup :attr:`.processes` which the microbes perform on domain entities


    """

    def __init__(self, features = None, processes = None, **kwargs):
        """
        Initialize a microbial group

        Args:
            features (dict): the definitions for :meth:`.add_feature_from`
            processes (dict): the definitions for :meth:`.add_process_from`

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in MicrobialGroup')
        kwargs['logger'] = self.logger

        super(MicrobialGroup, self).__init__(**kwargs)

        self._biomass = None

        #: container of the fipy Variables belonging to the microbes
        self.VARS = {}

        #: the features of the microbes, which are instances of
        # :class:`.ModelVariable`.
        self.features = {}

        #: the processes of the microbes, which are instances of
        #: :class:`~microbenthos.core.process.Process`.
        self.processes = {}

        if features:
            for fname, fdict in dict(features).items():
                self.add_feature_from(fname, **fdict)

        if processes:
            for pname, pdict in dict(processes).items():
                self.add_process_from(pname, **pdict)

        self.logger.debug('Initialized {}'.format(self))

    def __repr__(self):
        return '{}:Feat({}):Procs({})'.format(self.name,
                                              ','.join(self.features.keys()),
                                              ','.join(self.processes.keys()))

    def __getitem__(self, item):
        """
        Item getter to behave like a domain
        """
        if item in self.VARS:
            return self.VARS[item]
        else:
            return self.domain[item]

    def __contains__(self, item):
        if item in self.VARS:
            return True
        else:
            return item in self.domain

    def add_feature_from(self, name, **params):
        """
        Create a feature and add it it :attr:`.features`

        Args:
            name (str): name of the feature
            **params: parameters passed to :meth:`.from_dict`

        """
        # feature variable should be stored here, not on domain
        if params['cls'].endswith('Variable'):
            params['init_params']['create']['store'] = False
            self.logger.debug('Set variable store = False')

        self.logger.debug(
            'Dispatch init of feature {!r}: {}'.format(name, params))
        instance = self.from_dict(params)

        if name in self.features:
            self.logger.warning(
                'Overwriting feature {!r} with {}'.format(name, instance))

        self.logger.debug(
            '{} added feature {}: {}'.format(self, name, instance))
        self.features[name] = instance

    def add_process_from(self, name, **params):
        """
        Create a process and add it it :attr:`.processes`

        Args:
            name (str): name of the process
            **params: parameters passed to :meth:`.from_dict`

        """
        self.logger.debug('Dispatch init of process {!r}'.format(name, params))
        params['init_params']['name'] = '{}:{}'.format(self.name, name)
        instance = self.from_params(**params)

        if name in self.processes:
            self.logger.warning(
                'Overwriting process {!r} with {}'.format(name, instance))

        self.logger.debug(
            '{} added process {}: {}'.format(self, name, instance))
        self.processes[name] = instance

    @property
    def biomass(self):
        """
        The feature "biomass" stored in :attr:`.features`. This is considered
        as an essential
        feature for a microbial group. However, no error is raised if not
        defined currently.

        Returns:
            :class:`fipy.CellVariable`: biomass variable stored on the domain

        """
        ret = self.features.get('biomass')
        if ret is None:
            self.logger.warning(
                'Essential feature "biomass" of {} missing!'.format(self))
        else:
            if ret.var is not None:
                ret = ret.var
        return ret

    def on_domain_set(self):
        """
        Set up the domain on the microbial group.

        Note:
            Features, which are handlers for domain variables, receive the
            domain instances. However
            processes receive `self` as the domain, so that variable lookup
            happens first locally on
            the instance and then passed on to the domain.

        """

        for obj in self.features.values():
            self.logger.debug('Setting domain for {}'.format(obj))
            obj.domain = self.domain

        for obj in self.processes.values():
            self.logger.debug('Setting self as domain for {}'.format(obj))
            obj.domain = self

    def setup(self, **kwargs):
        """
        If the domain is available, then setup all the features and processes.

        Store any :class:`fipy.CellVariable` created in :attr:`.features`
        into :attr:`.VARS`.

        """
        self.logger.debug('Setup of {}'.format(self))
        if self.check_domain():
            for obj in itertools.chain(
                self.features.values(),
                self.processes.values()
                ):
                self.logger.debug('Setting up {}'.format(obj))
                obj.setup(**kwargs)

                if isinstance(obj, ModelVariable):
                    self.VARS[obj.name] = obj.var
                    self.logger.debug('Stored var {!r} into VARS'.format(obj))

    def on_time_updated(self, clocktime):
        """
        When model clock updated, delegate to feature and process instances
        """
        self.logger.debug('Updating {}'.format(self))
        for obj in itertools.chain(
            self.features.values(),
            self.processes.values()
            ):
            obj.on_time_updated(clocktime)

    def snapshot(self, base = False):
        """
        Returns a snapshot of the state with the structure:

            * "metadata"
                * "name": :attr:`.name`

            * "features"
                * "name" : :meth:`.snapshot()` of :attr:`.features`

            * "processes"
                * "name" : :meth:`.snapshot()` of :attr:`.processes`

        Returns:
            dict: state of the microbial group

        """
        self.logger.debug('Snapshot: {}'.format(self))
        self.check_domain()

        state = dict()
        meta = state['metadata'] = {}
        meta['name'] = self.name

        features = state['features'] = {}
        for name, obj in self.features.items():
            features[name] = obj.snapshot(base=base)

        processes = state['processes'] = {}
        for name, obj in self.processes.items():
            processes[name] = obj.snapshot(base=base)

        return state

    def restore_from(self, state, tidx):
        """
        Simply delegate to :meth:`~ModelVariable.restore_from` of the
        features and processes
        """

        for name, obj in self.features.items():
            obj.restore_from(state['features'][name], tidx)

        for name, obj in self.processes.items():
            obj.restore_from(state['processes'][name], tidx)
