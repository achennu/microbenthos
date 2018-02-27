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
            one=(('x', 'Ks', 'Ki'), 'x+Ks+Ki'),
            two=(' x Ks Ki', 'x+Ks*Ki'),
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
            ([('a+b', 1)], None),
            ],
        ids=(
            'string',
            'tuple-pair',
            'tuple-pairs'

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
        'formula',
        [
            'a+b',
            [('a+b', 1)],
            [('a+b', 'b>a')],
            [('a+b', 'b>a'), ('a-b', 'b<a')],
            [('a+b', 'b>bmax'), ('a-b', 'b<a')],

            ],
        ids=(
            'no-condition',
            'int-condition',
            'expr-condition',
            'expr-conditions',
            'condition-symbol',

            )
        )
    def test_add_piece(self, formula):

        e = Expression()
        items = e.parse_formula(formula)
        all_symbols = set()
        for expr, condition in items:
            e.add_piece(expr, condition)
            all_symbols.update({_ for _ in expr.atoms() if isinstance(_, sp.Symbol)})
            all_symbols.update({_ for _ in condition.atoms() if isinstance(_, sp.Symbol)})

        assert len(e._pieces) == len(items)

        assert e.symbols == all_symbols
