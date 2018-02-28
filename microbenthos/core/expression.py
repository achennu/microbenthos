import logging
from collections import Mapping

import sympy as sp


class Expression(object):
    """
    The class represents mathematical expressions that can be used to represent Processes in the
    model. This class allows to define piecewise functions and maintain the conditions as
    separate expressions.
    """
    _sympy_ns = {}

    def __init__(self, formula = None, name = None, namespace = None,
                 derived = None,
                 ):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))

        self.name = name or 'unnamed'
        self._sympy_ns = self._sympy_ns.copy()
        namespace = namespace or {}
        for name, itemdef in namespace.items():
            self._update_namespace(name,
                                   vars=itemdef['vars'],
                                   expr=itemdef['expr'])

        derived = derived or {}
        for name, dstr in derived.items():
            dexpr = self._sympify(dstr)
            self.logger.debug('Derived {!r}: {}'.format(name, dexpr))
            self._sympy_ns[name] = dexpr

        self._pieces = []
        self.base = None


        if formula:
            base, pieces = self.parse_formula(formula)
            self.base = base

            self.logger.debug('Added base expr {!r}'.format(base))

            for expr in pieces:
                self.add_piece(*expr)

        self.logger.debug(
            '{} created with base {!r} and {} pieces'.format(
                self, self.base, len(self._pieces)))

    def __repr__(self):
        return 'Expr({})'.format(self.name)

    def _update_namespace(self, name, vars, expr):
        self.logger.debug('Adding to namespace {!r}: {}'.format(name, expr))
        func = sp.Lambda(sp.symbols(vars), expr)
        self._sympy_ns[name] = func

    def parse_formula(self, formula):

        self.logger.debug('Parsing formula: {}'.format(formula))
        expressions = []

        if isinstance(formula, basestring):
            base = self._sympify(formula)

        elif isinstance(formula, Mapping):
            # keys are "base" expr, "pieces" with list of (expr, where) pairs
            base = self._sympify(formula.get('base', 1))
            for piece in formula.get('pieces', []):
                expr = piece['expr']
                cond = piece['where']
                expressions.append((self._sympify(expr), self._sympify(cond)))

        self.logger.debug('Parsed (expr, cond): {}'.format(expressions))
        return base, expressions

    def _sympify(self, formula):
        try:
            self.logger.debug('Sympify {!r}'.format(formula))
            expr = sp.sympify(formula, locals=self._sympy_ns)
            return expr
        except (sp.SympifyError, SyntaxError):
            self.logger.error('Sympify failed on {}'.format(formula))
            raise ValueError('Could not parse formula {}'.format(formula))

    def add_piece(self, expr, condition):
        """
        Add the `expr` as a piecewise term where `condition` is valid

        Args:
            expr (:class:`~sp.Expr`): The sympy expression
            condition (:class:`~sp.Expr`): The condition where the expression is active

        """
        self.logger.debug('Adding term {!r} for condition {!r}'.format(
            expr, condition
            ))

        if not isinstance(expr, sp.Expr):
            raise ValueError('expr {!r} not a sympy Expr, but {}'.format(expr, type(expr)))

        if not isinstance(condition, (sp.Expr, int)):
            raise ValueError('condition {!r} not a sympy Expr, but {}'.format(condition,
                                                                              type(condition)))

        self._pieces.append((expr, condition))

    def symbols(self):
        return {_ for _ in self.expr().atoms() if isinstance(_, sp.Symbol)}

    def expr(self):
        pieces = sum(e * c for e, c in self._pieces)
        if pieces:
            return self.base * pieces
        else:
            return self.base

    def diff(self, *args):
        if self._pieces:
            ret = sum((self.base * e).diff(*args) * c for e, c in self._pieces)
        else:
            ret = self.base.diff(*args)
        return ret

    __call__ = expr
