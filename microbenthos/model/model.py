import logging

from sympy import Lambda, symbols

from microbenthos import Entity, ExprProcess


class MicroBenthosModel(object):
    """
    Class that represents the model, as a container for all the entities in the domain
    """

    def __init__(self, definition):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Initializing {}'.format(self.__class__.__name__))

        self.logger.debug('Definition: {}'.format(definition.keys()))

        required = set(('domain', 'environment'))
        keys = set(definition.keys())
        missing = required.difference(keys)
        if missing:
            self.logger.error('Required definition not found: {}'.format(missing))

        self.domain = None
        self.microbes = {}
        self.env = {}

        # Load up the formula namespace
        if 'formulae' in definition:
            formulae_ns = {}
            self.logger.info('Creating formulae')
            for name, fdict in definition['formulae'].items():
                func = Lambda(symbols(fdict['variables']), fdict['expr'])
                self.logger.debug('Formula {!r}: {}'.format(name, func))
                formulae_ns[name] = func

            ExprProcess._sympy_ns.update(formulae_ns)

        # Create the domain
        self.logger.info('Creating the domain')
        domain_def = definition['domain']
        self.logger.debug(domain_def)
        self.domain = Entity.from_dict(domain_def)

        # create the environment
        env_def = definition['environment']
        self.logger.info('Creating env: {}'.format(env_def.keys()))
        for name, pdict in env_def.items():
            self.logger.debug('Creating {}'.format(name))
            entity = Entity.from_dict(pdict)
            entity.set_domain(self.domain)
            entity.setup()
            self.env[name] = entity
            self.logger.info('Env entity {} = {}'.format(name, entity))
            assert entity.check_domain()

        # create the microbes
        microbes_def = definition.get('microbes')
        if microbes_def:
            self.logger.info('Creating microbes: {}'.format(microbes_def.keys()))
            for name, pdict in microbes_def.items():
                self.logger.debug('Creating {}'.format(name))
                entity = Entity.from_dict(pdict)
                entity.set_domain(self.domain)
                entity.setup()
                self.microbes[name] = entity
                self.logger.info('Microbes {} = {}'.format(name, entity))

        # create equations
        eqndef = definition.get('equations')
        for eqnname, eqndef in eqndef.items():
            self.create_equation(eqnname, **eqndef)

    def snapshot(self, base = False):
        """
        Create a snapshot of the model state.

        This method recursively calls the :meth:`snapshot` method of all contained entities,
        and compiles them into a nested dictionary. The dictionary has the structure of the
        model, except that that two reserved keys `data` and `metadata` indicate the presence of
        a numeric array or the metadata for the corresponding entity. This should be useful to
        parse this for serialization in hierarchical formats (like :mod:`h5py`) or flat formats
        by de-nesting as required. In the latter case, disambiguation of identically named variables
        will have to be performed first. Each snapshot, should be possible to plot out
        graphically as it contains all the metadata associated with it.

        Args:
            base (bool): Whether the entities should be converted to base units?

        Returns:
            A dictionary of the model state (domain, env, microbes)
        """
        self.logger.debug('Creating model snapshot')
        state = {}
        state['domain'] = self.domain.snapshot(base=base)

        env = state['env'] = {}
        microbes = state['microbes'] = {}
        for name, obj in self.env.items():
            self.logger.debug('Snapshotting: {} --> {}'.format(name, obj))
            ostate = obj.snapshot(base=base)
            env[name] = ostate

        for name, obj in self.microbes.items():
            self.logger.debug('Snapshotting: {} --> {}'.format(name, obj))
            ostate = obj.snapshot(base=base)
            microbes[name] = ostate

        self.logger.info('Created model snapshot')
        return state

    __getstate__ = snapshot

    def create_equation(self, name, var, transient, sources, diffusion = None, ):

        self.logger.info('Creating equation {!r}'.format(name))
        self.logger.debug('transient: {}'.format(transient))
        self.logger.debug('sources: {}'.format(sources))
        self.logger.debug('diffusion: {}'.format(diffusion))

        from fipy import TransientTerm, DiffusionTerm, CellVariable

        var = self._get_eqn_obj(**var)

        if not isinstance(var, CellVariable):
            raise RuntimeError('Var {!r} is {}, not CellVariable'.format(var, type(var)))

        term_transient = TransientTerm(var=var, coeff=transient.get('coeff', 1))
        self.logger.debug('Transient term: {}'.format(term_transient))

        if diffusion:
            C = self._create_diffusion_coeff(**diffusion)
            term_diffusion = DiffusionTerm(coeff=C, var=var)
        else:
            term_diffusion = None

        self.logger.debug('Diffusion term: {}'.format(term_diffusion))

        source_terms = []
        for s in sources:
            sterm = self._create_source_term(var=var, **s)
            if sterm is not None:
                source_terms.append(sterm)

        self.logger.debug('Equation with {} source terms'.format(len(source_terms)))

        if term_diffusion:
            source_terms.insert(0, term_diffusion)

        eqn = term_transient == sum(source_terms)
        self.logger.info('Final equation: {}'.format(eqn))
        return eqn

    def _create_diffusion_coeff(self, coeff):
        self.logger.debug('Creating diffusion coeff from {}'.format(type(coeff)))
        if isinstance(coeff, dict):
            try:
                coeff_ = Entity.from_dict(coeff)
                coeff_.set_domain(self.domain)
                return coeff_.evaluate()
            except:
                self.logger.error('Could not create diffusion coeff from dict', exc_info=True)
                raise RuntimeError('Error creating diffusion coeff')

        else:
            raise NotImplementedError('Input of type {} for diffusion coeff'.format(type(coeff)))

    def _create_source_term(self, name, store, var, **kwargs):

        from fipy import ImplicitSourceTerm

        self.logger.info('Creating source for {}.{}'.format(store, name))

        try:
            sobj = self._get_eqn_obj(store, name)
            if not isinstance(sobj, ExprProcess):
                raise NotImplementedError('Source term from type {!r}'.format(type(sobj)))

        except ValueError:
            self.logger.warning('Found no source for {}.{}'.format(store, name))
            return

        sterm = sobj.evaluate()
        C = kwargs.get('coeff')
        if C is not None:
            sterm *= C
        self.logger.debug('Created source term: {!r}'.format(sterm))

        dvars = sobj.dependent_vars()
        ovars = dvars.difference(set([var.name]))
        if ovars:
            self.logger.debug('Making implicit because of other vars: {}'.format(ovars))
            term_source = ImplicitSourceTerm(coeff=sterm, var=var)
        else:
            term_source = sterm

        self.logger.debug('Created {!r} source: {!r}'.format(name, sterm))
        return term_source

    def _get_eqn_obj(self, store, name, **kwargs):

        self.logger.debug('Getting {!r} from {!r}'.format(name, store))
        parts = store.split('.')

        S = self
        for p in parts:
            # self.logger.debug('Getting {!r} from {}'.format(p, S))
            S_ = getattr(S, p, None)
            if S_ is None:
                try:
                    S = S[p]
                except KeyError:
                    raise ValueError('Unknown store {!r} for {!r}'.format(p, name))
            else:
                S = S_

        # self.logger.debug('Getting obj {!r} from store {!r}'.format(name, S))
        obj = S[name]
        self.logger.debug('Got obj: {!r}'.format(obj))
        return obj
