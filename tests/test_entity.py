import pytest
from fipy import PhysicalField

from microbenthos import Entity, SedimentDBLDomain, DomainEntity


class TestEntity:
    def test_init(self):
        e = Entity()
        assert e

    def test_update_time(self):
        # update to clock time
        e = Entity()
        with pytest.raises(TypeError):
            e.update_time()
        e.update_time(2)
        e.update_time(3.5)
        e.update_time(PhysicalField('35 s'))

    @pytest.mark.xfail(reason='not implemented')
    def test_from_params(self):
        raise NotImplementedError('For Entity.from_params()')

    @pytest.mark.xfail(reason='not implemented')
    def test_from_dict(self):
        raise NotImplementedError('For Entity.from_dict()')


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
        # should be not implemented

        e = DomainEntity()
        with pytest.raises(NotImplementedError):
            e.setup()
