import pytest
from microbenthos.model import MicroBenthosModel, from_dict
from microbenthos.domain import SedimentDBLDomain
import yaml

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
def model():
    definition = from_dict(yaml.load(MODEL_DEF))
    m = MicroBenthosModel.from_definition(definition)
    return m


class TestModel:

    def test_init_empty(self):
        m = MicroBenthosModel()
        assert m

    def test_init_domain(self, domain):

        m = MicroBenthosModel(domain)
        assert m
        assert m.domain

    def test_from_definition(self):

        mdict = yaml.load(MODEL_DEF)
        mdict = from_dict(mdict)
        m = MicroBenthosModel.from_definition(mdict)

        assert m.domain
        assert m.all_entities_setup

    def test_snapshot(self, model):

        state = model.snapshot()

        statekeys = ('env', 'microbes', 'domain', 'equations')
        assert set(statekeys) == set(state)

        microbekeys = set(model.microbes)
        assert microbekeys == set(state['microbes'])

        envkeys = set(model.env)
        assert envkeys == set(state['env'])

        eqnkeys = set(model.equations)
        assert eqnkeys == set(state['equations'])

        assert state['equations'] == model.equation_defs

    @pytest.mark.xfail(reason='not implemented')
    def test_add_equation(self, model):
        # check that add quation input forms are correct
        # a tuple of (modelpath, coeff) where coeff is int, float
        # check that Equation obj is created
        # check that equation definition is saved
        raise NotImplementedError
