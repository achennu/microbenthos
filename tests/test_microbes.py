import pytest

from microbenthos import MicrobialGroup

VARdict = dict(
    cls='Variable',
    init_params=dict(
        name='biomass',
        create=dict(value=35)
        ))

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
