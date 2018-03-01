import io

import mock
import pytest
import yaml
from fipy import Variable, PhysicalField
from microbenthos import MicroBenthosModel, validate_dict, SedimentDBLDomain
from microbenthos.model.model import ModelClock

MODEL_DEF = """

domain:
    cls: SedimentDBLDomain
    init_params:
        cell_size: !unit 50 mum
        sediment_length: !unit 10 mm
        dbl_length: !unit 2 mm
        porosity: 0.6
        
formulae:

    inhibition_response:
        variables: [x, Kmax, Khalf]
        expr: (Kmax - x) / (2*Kmax - Khalf - x) * (x < Kmax)
        
environment:

    oxy:
        cls: Variable
        init_params:
            name: oxy
            create:
                hasOld: true
                value: !unit 0.0 mol/m**3

            constraints:
                top: &oxy_top !unit 1e-12 mol/l
                bottom: &oxy_bottom !unit 0 mol/l

            seed:
                profile: linear
                params:
                    start: *oxy_top
                    stop: *oxy_bottom

    h2s:
        cls: Variable
        init_params:
            name: h2s
            create:
                hasOld: true
                value: !unit 0.0 mol/m**3

            constraints:
                top: &h2s_top !unit 0 mol/l
                bottom: &h2s_bottom !unit 1e-3 mol/l

            seed:
                profile: linear
                params:
                    start: *h2s_top
                    stop: *h2s_bottom
                    
    D0_oxy:
        cls: Variable
        init_params:
            name: D0_oxy
            create:
                value: !unit 1.3888e-9 m**2/s

    D_oxy:
        cls: ExprProcess
        init_params:
            formula: porosity * D0_oxy
            varnames:
                - porosity
                - D0_oxy
                
    D0_h2s:
        cls: Variable
        init_params:
            name: D0_h2s
            create:
                value: !unit 8.3333e-10 m**2/s

    D_h2s:
        cls: ExprProcess
        init_params:
            formula: porosity * D0_h2s
            varnames:
                - porosity
                - D0_h2s
                
microbes:
    cyano:
        init_params:
            name: cyano
            features:
                biomass:
                    init_params:
                        name: biomass
                        create:
                            value: !unit 0 mg/cm**3
                            hasOld: true
                        seed:
                            profile: normal
                            params:
                                loc: !unit 1 mm
                                scale: !unit 2 mm
                                coeff: !unit 12 mg/cm**3
                                
            processes:
                oxyPS:
                    init_params:
                        formula: Qmax * biomass * sed_mask
                        varnames:
                            - biomass
                            - sed_mask
                        params:
                            Qmax: !unit 0.00841 mol/g/h
                    
                        responses:
                            inhibit(oxy):
                                cls: ExprProcess
                                init_params:
                                    formula: inhibition_response(oxy, Kmax, Khalf)
                                    varnames:
                                        - oxy
                                    params:
                                        Kmax: !unit "0.8e-3 mol/l"
                                        Khalf: !unit "0.7e-3 mol/l"


"""


@pytest.fixture()
def domain():
    return SedimentDBLDomain()


@pytest.fixture()
def model_dict():
    return validate_dict(yaml.load(MODEL_DEF), key='model')

@pytest.fixture()
def model():
    pytest.xfail(reason='Inputs not updated to new schema yet')
    m = MicroBenthosModel.from_dict(yaml.load(MODEL_DEF))
    return m


class TestModel:
    def test_init_empty(self):
        m = MicroBenthosModel()
        assert m

    def test_init_domain(self, domain):

        m = MicroBenthosModel(domain=domain)
        assert m
        assert m.domain

    @pytest.mark.xfail(reason='Inputs not updated to new schema yet')
    @pytest.mark.parametrize('obj', [
        MODEL_DEF,
        io.StringIO(unicode(MODEL_DEF)),
        yaml.load(io.StringIO(unicode(MODEL_DEF)))
        ],
         ids=('string', 'stream', 'dict'))
    def test_create_from(self, obj):
        m = MicroBenthosModel.create_from(obj)
        assert m.domain
        assert m.all_entities_setup

    def test_snapshot(self, model):

        state = model.snapshot()

        statekeys = ('env', 'microbes', 'domain', 'equations', 'time')
        assert set(statekeys) == set(state)

        microbekeys = set(model.microbes)
        assert microbekeys == set(state['microbes'])

        envkeys = set(model.env)
        assert envkeys == set(state['env'])

        eqnkeys = set(model.equations)
        assert eqnkeys == set(state['equations'])
        for eqnstate in state['equations'].values():
            assert set(eqnstate) == {'transient', 'diffusion', 'sources'}

        assert set(state['time']) == {'data'}

    def test_update_vars(self, model, model_dict):

        hasold_list = []
        for name, odef in model_dict['environment'].items():
            print('Checking env.{} : {}'.format(name, odef.items()))

            if odef['cls'] == 'Variable' and odef['init_params'].get('create', {}).get('hasOld'):
                hasold_list.append('env.{}'.format(name))

        for name, mdef in model_dict['microbes'].items():
            print('Checking micrboes.{}'.format(name))
            for feat, fdef in mdef['init_params']['features'].items():
                if fdef['cls'] == 'Variable' and fdef['init_params'].get(
                    'create', {}).get('hasOld'):
                    hasold_list.append('microbes.{}.features.{}'.format(name, feat))

        updated = model.update_vars()
        assert set(updated) == set(hasold_list)

    @pytest.mark.parametrize(
        'transient, diffusion, sources, error',
        [
            (
                None,
                None,
                None,
                ValueError
                ),
            (
                ('env.oxy', 1),
                None,
                None,
                ValueError
                # either source or diffusion must be present
                ),

            (
                ('domain.oxy', 1),
                ('env.D_oxy', 1),
                None,
                None
                # only diffusion
                ),
            (
                ('domain.oxy', 1),
                None,
                [('microbes.cyano.processes.oxyPS', 3)],
                None
                # only sources
                ),
            (
                ('domain.oxy', 1),
                ('env.D_oxy', 1),
                [('microbes.cyano.processes.oxyPS', 3)],
                None
                # diffusion and sources
                ),
            (
                ('domain.oxy', 1),
                ('env.D_oxy', 1),
                ('microbes.cyano.processes.oxyPS', 3),
                ValueError
                # sources should be list of tuples
                ),
            (
                ('oxy', 1),
                ('env.D_oxy', 1),
                ('microbes.cyano.processes.oxyPS', 3),
                ValueError
                # transient is not dotted path, error in model.get_object
                ),

            ]
        )
    def test_add_equation(self, model, transient, diffusion, sources, error):
        # check that add quation input forms are correct
        # a tuple of (modelpath, coeff) where coeff is int, float
        # check that Equation obj is created
        # check that equation definition is saved

        if error:
            with pytest.raises(error):
                model.add_equation('eqn',
                                   transient=transient,
                                   diffusion=diffusion,
                                   sources=sources)

        else:

            model.add_equation('eqn',
                               transient=transient,
                               diffusion=diffusion,
                               sources=sources)
            assert 'eqn' in model.equations
            with pytest.raises(RuntimeError):
                # eqn already created raises runtime error
                model.add_equation('eqn',
                                   transient=transient,
                                   diffusion=diffusion,
                                   sources=sources)


class TestModelClock:
    def test_init(self, model):
        with pytest.raises(TypeError):
            assert ModelClock()

        clock = ModelClock(model)
        assert clock is not None
        assert clock.value == 0
        assert isinstance(clock, Variable)

    def test_model_clock(self, model):
        assert isinstance(model.clock, Variable)
        assert model.clock.unit.name() == 'h'

    @pytest.mark.parametrize('dt, error', [
        (-1, ValueError),
        (0, ValueError),
        (1, None),
        (PhysicalField('3 s'), None),
        (PhysicalField('2 min'), None),
        (PhysicalField('1 h'), None),

        ])
    def test_increment(self, model, dt, error):

        if error:
            with pytest.raises(error):
                model.clock.increment_time(dt)
            return

        old = model.clock.value.copy()
        print('Incrementing {} by {}'.format(old, dt))
        model.clock.increment_time(dt)
        new = model.clock.value

        assert new == old + PhysicalField(dt, 's'), 'Added {} to {} failed'.format(
            PhysicalField('s'), old)

    @pytest.mark.parametrize('t, error', [
        (-1, ValueError),
        (0, None),
        (1, None),
        (PhysicalField('3 s'), None),
        (PhysicalField('2 min'), None),
        (PhysicalField('1 h'), None),

        ])
    def test_set_time(self, model, t, error):

        if error:
            with pytest.raises(error):
                model.clock.set_time(t)
            return

        print('Setting time to {}'.format(t))
        model.clock.set_time(t)
        new = model.clock.value

        assert new == PhysicalField(t, 'h')

    def test_model_update_called(self, model):

        with mock.patch.object(model, 'on_time_updated') as mockobj:
            model.clock.set_time(3)
            mockobj.assert_called_once()

            mockobj.reset_mock()

            model.clock.increment_time(1)
            mockobj.assert_called_once()

    @mock.patch('microbenthos.Entity.on_time_updated', autospec=True)
    def test_entity_update_called(self, mockobj, model):

        count = len(model.env)
        for m in model.microbes.values():
            count += len(m.features)

        model.clock.set_time(3)

        mockobj.assert_called_with(mock.ANY, PhysicalField(3, 'h'))
        print(mockobj.mock_calls)
        assert len(mockobj.mock_calls) == count
