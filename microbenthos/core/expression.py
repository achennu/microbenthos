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
                 **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        # kwargs['logger'] = self.logger
        # super(Expression, self).__init__(**kwargs)

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

        self.symbols = set()
        self._pieces = []
        self.base = None


        if formula:
            base, pieces = self.parse_formula(formula)
            base_symbols = {_ for _ in base.atoms() if isinstance(_, sp.Symbol)}
            self.symbols.update(base_symbols)
            self.base = base

            self.logger.debug('Added base expr {!r} with symbols: {}'.format(base, base_symbols))

            for expr in pieces:
                self.add_piece(*expr)

        self.logger.debug(
            '{} created with base {!r} and {} pieces and symbols: {}'.format(
                self, self.base, len(self._pieces), self.symbols))

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
            # expr = self._sympify(formula)
            # cond_ = sp.sympify(1)
            # expressions.append((expr, cond_))
            base = self._sympify(formula)

        elif isinstance(formula, (tuple, list)):
            # each item should be a (formula, condition) pair
            ok = all(len(item) == 2 for item in formula)
            if not ok:
                self.logger.error('Formula list improper: {}'.format(formula))
                raise ValueError('Formula as list should be pairs of (formula, condition)!')

            for form, condition in formula:
                expr = self._sympify(form)
                cond_ = self._sympify(condition)
                expressions.append((expr, cond_))

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

        for s in (expr, condition):
            symbols = {_ for _ in s.atoms() if isinstance(_, sp.Symbol)}
            self.symbols.update(symbols)

        self._pieces.append((expr, condition))

    def symbols(self):
        return {_ for _ in self.expr().atoms() if isinstance(_, sp.Expr)}

    def expr(self):
        full = self.base * sum(e * c for e, c in self._pieces)
        return full#.simplify()

    def diff(self, *args):
        return sum((self.base*e).diff(*args) * c for e, c in self._pieces).simplify()
