import pytest
from microbenthos.base import Entity
from microbenthos.domain import SedimentDBLDomain, PhysicalField


class TestEntity:

    def test_init(self):
        e = Entity()
        assert e
        assert not e.features

    def test_add_domain(self):
        e = Entity()
        D = SedimentDBLDomain()

        with pytest.raises(TypeError):
            e.domain = object()

        e.domain = D

        assert e.domain is D

        with pytest.raises(RuntimeError):
            e.domain = D

    def test_setup(self):
        # should be not implemented

        e = Entity()
        with pytest.raises(NotImplementedError):
            e.setup()

    def test_update_time(self):
        # update to clock time
        e = Entity()
        with pytest.raises(TypeError):
            e.update_time()
        e.update_time(2)
        e.update_time(3.5)
        e.update_time(PhysicalField('35 s'))








