
from microbenthos.utils.yaml_loader import yaml, PhysicalField


def test_load_unit():

    val = "35 mol/l"
    s = """
    km: !unit {}
    """.format(val)

    val_ = yaml.load(s)['km']

    assert val_ == PhysicalField(val)


def test_dump_unit():
    inp = "40 mol/l"
    P = PhysicalField(inp)
    # PhysicalField with str input coerces value to float

    expected = "!unit '{} {}'".format(P.value, P.unit.name())
    s = yaml.dump(P).strip()

    assert s == expected


