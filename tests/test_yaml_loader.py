import pytest
from fipy import PhysicalField
from microbenthos.utils import yaml

def test_load_unit():

    val = "35 mol/l"
    s = """
    km: !unit {}
    """.format(val)

    val_ = yaml.unsafe_load(s)['km']

    assert val_ == PhysicalField(val)


def test_dump_unit():
    inp = "40 mol/l"
    P = PhysicalField(inp)
    # PhysicalField with str input coerces value to float

    expected = "!unit '{} {}'".format(P.value, P.unit.name())
    s = yaml.dump(P).strip()

    assert s == expected

@pytest.mark.parametrize('inp, num', [
    # the two commented cases fail due to a PyYaml bug
    # see: https://stackoverflow.com/a/30462009
    # this sort of input in yaml files are handled by the MicroBenthosSchemaValidator class
    # by coercing to float
    ('1e-6', 1e-6),
    ('1e-8', 1e-8),
    # ('1.0e-6', 1.0e-6),
    ('-1e6', -1e6),
    # ('-1.3e-6', -1.3e-6),
    ('1e3', 1e3),
    ('1.0e3', 1e3),

    ])
def test_exp_notation(inp, num):
    val = yaml.unsafe_load(inp)
    assert val == inp


