import pytest
import copy
from microbenthos import MicrobialGroup, SedimentDBLDomain

VARdict = dict(
    cls='Variable',
    init_params=dict(
        name='biomass',
        create=dict(value=35)
        ))
VARdict2 = copy.deepcopy(VARdict)
VARdict2['init_params']['name'] = 'abcd'

PROCdict = dict(
    cls='ExprProcess',
    init_params=dict(
        formula='a',
        varnames=['a']
        )
    )


class TestMicrobialGroup:
    def test_init_empty(self):
        with pytest.raises(TypeError):
            MicrobialGroup()

    @pytest.mark.parametrize(
        'features, err',
        [(dict(), RuntimeError),
         (dict(not_biomass=VARdict.copy()), RuntimeError),
         (dict(biomass=VARdict.copy()), None),
         (dict(biomass=VARdict.copy(),
               pigment=VARdict.copy()), None),
         ],
        )
    def test_init_features(self, features, err):
        if err is None:
            m = MicrobialGroup('bugs', features=features)
            assert m
            assert m.biomass is not None
            for k in features:
                assert k in m.features

        else:
            with pytest.raises(err):
                m = MicrobialGroup('bugs', features=features)

    @pytest.mark.parametrize(
        'processes, err',
        [(dict(), None),
         (dict(p1=PROCdict.copy(), p2=PROCdict.copy()), None),
         ],
        )
    def test_init_processes(self, processes, err):
        F = dict(biomass=VARdict)
        if err is None:
            m = MicrobialGroup('bugs', features=F, processes=processes)
            assert m
            for k in processes:
                assert k in m.processes

        else:
            with pytest.raises(err):
                m = MicrobialGroup('bugs', features=F, processes=processes)

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

        m = MicrobialGroup('bugs', features=features, processes=processes)
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
