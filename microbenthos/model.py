import logging
from sympy import Lambda, symbols
from microbenthos import Entity, ExprProcess, Process


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
        self.environment = {}

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


        # create the microbes
        env_def = definition['environment']
        self.logger.info('Creating environment: {}'.format(env_def.keys()))
        for name, pdict in env_def.items():
            self.logger.debug('Creating {}'.format(name))
            entity = Entity.from_dict(pdict)
            entity.set_domain(self.domain)
            entity.setup()
            self.environment[name] = entity
            self.logger.info('Env entity {} = {}'.format(name, entity))


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




