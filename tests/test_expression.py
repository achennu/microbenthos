import pytest
import sympy as sp

from microbenthos.core.expression import Expression


class TestExpression:
    def test_init(self):

        e = Expression()
        assert not e._pieces

        e = Expression('a')
        assert e

        e = Expression('a', 'mine')
        assert e.name == 'mine'

    def test__update_namespace(self):
        ns = dict(
            one=(dict(vars=('x', 'Ks', 'Ki'), expr='x+Ks+Ki')),
            two=(dict(vars=' x Ks Ki', expr='x+Ks*Ki')),
            )
        e = Expression('a', namespace=ns)
        for n in ns:
            assert n in e._sympy_ns
            f = e._sympy_ns[n]
            assert isinstance(f, sp.Lambda)

    @pytest.mark.parametrize(
        'formula,err',
        [
            ('a+b', None),
            (('a+b', 1), ValueError),
            (dict(base='a+b', ), None),
            (dict(base='a+b', pieces=('3', 'a>3')), TypeError),
            (dict(base='a+b', pieces=[('3', 'a>3')]), TypeError),
            (dict(base='a+b', pieces=[dict(expr='3', where='a>3')]), None),
            ],
        ids=(
            'string',
            'tuple',
            'base-only',
            'pieces-tuple',
            'pieces-list-tuple',
            'pieces-list-dict',
            )
        )
    def test_parse_formula(self, formula, err):

        e = Expression()

        if err:
            with pytest.raises(err):
                e.parse_formula(formula)

        else:
            parsed = e.parse_formula(formula)
            assert parsed

    @pytest.mark.parametrize(
        'pieces',
        [
            [('a+b', 1)],
            [('a+b', 'b>a')],
            [('a+b', 'b>a'), ('a-b', 'b<a')],
            [('a+b', 'b>bmax'), ('a-b', 'b<a')],

            ],
        ids=(
            'int-condition',
            'expr-condition',
            'expr-conditions',
            'condition-symbol',

            )
        )
    def test_add_piece(self, pieces):

        e = Expression()
        for piece in pieces:
            e.add_piece(*[sp.sympify(_) for _ in piece])

        assert len(e._pieces) == len(pieces)
