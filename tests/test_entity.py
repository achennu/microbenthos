import pytest
from fipy import PhysicalField

from microbenthos import Entity, SedimentDBLDomain, DomainEntity

PF = PhysicalField


class TestEntity:
    def test_init(self):
        e = Entity()
        assert e

    def test_update_time(self):
        # update to clock time
        e = Entity()
        with pytest.raises(TypeError):
            e.on_time_updated()

        e.on_time_updated(2)
        e.on_time_updated(3.5)
        e.on_time_updated(PhysicalField('35 s'))
        # should this raise an error? No, because this is only reacts to the model clock
        e.on_time_updated(PF('5 kg'))

    def test_from_params(self):
        NAME = 'holla'
        params = dict(
            cls='Entity',
            init_params=dict(name=NAME)
            )
        e = Entity.from_params(**params)
        assert e.name == NAME

    def test_from_dict(self):
        NAME = 'holla'
        params = dict(
            cls='Entity',
            init_params=dict(name=NAME)
            )
        e = Entity.from_dict(params)
        assert e.name == NAME


class TestDomainEntity:
    def test_add_domain(self):
        e = DomainEntity()
        D = SedimentDBLDomain()

        # with pytest.raises(TypeError):
        #     e.domain = tuple()
        # This no longer raises a TypeError, but just issues a log warning

        e.domain = D

        assert e.domain is D

        with pytest.raises(RuntimeError):
            e.domain = D

    def test_setup(self):
        # should be not implemented, but raises no error
        e = DomainEntity()
        e.setup()
        assert True
