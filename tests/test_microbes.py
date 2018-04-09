import copy

import pytest
from microbenthos import MicrobialGroup, SedimentDBLDomain

VARdict = dict(
    cls='ModelVariable',
    init_params=dict(
        name='biomass',
        create=dict(value=35)
        ))
VARdict2 = copy.deepcopy(VARdict)
VARdict2['init_params']['name'] = 'abcd'

PROCdict = dict(
    cls='Process',
    init_params=dict(
        expr=dict(
            formula='a**2 * biomass', ),
        params = dict(a=3)
        )
    )


class TestMicrobialGroup:
    def test_init_empty(self):
        m = MicrobialGroup()
        assert m.name == 'unnamed'

    @pytest.mark.parametrize(
        'features, err',
        [(dict(), None),
         (dict(not_biomass=VARdict.copy()), None),
         (dict(biomass=VARdict.copy()), None),
         (dict(biomass=VARdict.copy(),
               pigment=VARdict.copy()), None),
         ],
        )
    def test_init_features(self, features, err):
        if err is None:
            m = MicrobialGroup(features=features)
            assert m
            if 'biomass' in features:
                assert m.biomass is not None
            for k in features:
                assert k in m.features

        else:
            with pytest.raises(err):
                m = MicrobialGroup(features=features)

    @pytest.mark.parametrize(
        'processes, err',
        [(dict(), None),
         (dict(p1=PROCdict.copy(), p2=PROCdict.copy()), None),
         ],
        )
    def test_init_processes(self, processes, err):
        F = dict(biomass=VARdict)
        if err is None:
            m = MicrobialGroup(features=F, processes=processes)
            assert m
            for k in processes:
                assert k in m.processes

        else:
            with pytest.raises(err):
                m = MicrobialGroup(features=F, processes=processes)

    @pytest.mark.parametrize(
        'features, processes,err',
        [
            (
                dict(biomass=VARdict.copy(),
                     another=VARdict.copy()),
                None,
                None),
            (
                dict(biomass=VARdict.copy(),
                     another=VARdict2.copy()),
                None,
                None)
            ],
        ids=['varname_repeat',
             'varname_unique',
             ]
        )
    def test_setup(self, features, processes, err):
        # Test that for microbes, the feature variables are not stored on the domain
        # Also multiple features with same variable name will not raise an error

        domain = SedimentDBLDomain()

        m = MicrobialGroup(features=features, processes=processes)
        m.set_domain(domain)

        if err is None:
            m.setup()
            for feat in m.features.values():
                assert feat.name not in domain
                assert feat.name in m

            for fname, fdict in features.items():
                vname = fdict['init_params']['name']
                assert vname in m
                if fname != vname:
                    assert fname not in m
                    assert fname in m.features

        else:
            with pytest.raises(err):
                m.setup()

    @pytest.mark.parametrize('features', [
        dict(biomass=VARdict.copy()),
        (dict(biomass=VARdict.copy(), pigment=VARdict2.copy())),
        ],
                             ids=('1feat', '2feat')
                             )
    @pytest.mark.parametrize('processes',
                            [
                                dict(proc1=PROCdict.copy()),
                                dict(proc1=PROCdict.copy(),
                                     proc2=PROCdict.copy()
                                     ),
                                ],
                            ids=('1proc', '2proc')
                            )
    def test_snapshot(self, features, processes):

        domain = SedimentDBLDomain()
        domain.create_var('biomass', value=1, unit='mg/cm**3')

        m = MicrobialGroup(features=features, processes=processes)
        m.set_domain(domain)
        m.setup()

        state = m.snapshot()

        statekeys = ('metadata', 'features', 'processes')
        assert set(statekeys) == set(state.keys())

        featkeys = set(m.features)
        assert featkeys == set(state['features'])

        prockeys = set(m.processes)
        assert prockeys == set(state['processes'])


