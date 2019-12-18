import logging
from collections.abc import Mapping

import sympy as sp


class Expression(object):
    """
    Representation of mathematical expressions as strings to be used for definition of processes
    in the model domain.

    The class relies on :mod:`sympy` to parse the formula, but allows the definition of
    piecewise functions (in :meth:`.add_piece`) to maintain differentiability of each piece. Calling
    :meth:`.expr` returns the combined expression of all the pieces, and :meth:`.diff` returns
    the derivative with respect to a symbol of all the pieces.

    Note:
        As :func:`~sympy.core.sympify.sympify` uses :func:`eval` internally, the same caveats
        apply on processing unvalidated inputs as listed in the sympy docs.

    """
    #: the namespace used for :meth:`sympy.sympify`
    _sympy_ns = {}

    def __init__(self, formula = None, name = None, namespace = None,
                 derived = None,
                 ):
        """
        Create an expression with a symbolic representation

        Args:
            formula (str, dict): Definition of a base and possibly piecewise function
                symbolically. This is processed by :meth:`.parse_formula`.

            name (str): An identifier for the instance

            namespace (None, dict): A mapping of symbolic names to expressions to be added to the
                :attr:`_sympy_ns`. The structure of the dictionary should be

                * name (str)
                    * vars (list) : symbols in the `expr` to be passed to
                      :func:`~sympy.core.symbol.symbols`
                    * expr (str) : the expression to be created with
                      :class:`~sympy.core.function.Lambda`

            derived (None, dict): A mapping of symbol to expressions to be
                added to the :attr:`._sympy_ns` used. This is useful when a complicated
                subexpression needs to be specified separately.

        Examples:

            .. code-block:: python

                Expression(formula = 'x**2 + 3*y')
                Expression(formula=dict(base="x**2 + 3*y"))
                Expression(formula=dict(
                                base="x**2 + 3*y",
                                pieces = [
                                        dict(where="y>0", expr= "1"),
                                        dict(where="y<=0", expr= "0.25*x"),
                                        ]))
                Expression(formula="3x * myXvar",
                           derived=dict(myXvar="sin(x)**(x-0.5/(2-x))"))

        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))

        self.name = name or 'unnamed'

        #: the namespace used for :func:`~sympy.core.sympify.sympify`
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
        #: the base expression as a sympy Expr
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
        """
        Process the formula and return symbolic expressions for the base and any pieces.

        Args:
            formula (str, dict): Input should be one of

                 * str: which is then only a :attr:`.base` expression with no
                   piece-wise definitions.

                 * dict: with the structure

                    * ``"base"``: the base expression string

                    * ``"pieces"``: a list of dicts where each dict has the structure
                        * ``"where"``: str that expresses the condition for the
                          functional space
                        * ``"expr:`` The value of the function in that space

        Returns:
            (base, pieces): the base expression and a list of piece-wise expressions

        Raises:
            ValueError: Improper input for `formula`

        """
        self.logger.debug('Parsing formula: {}'.format(formula))
        expressions = []

        if isinstance(formula, str):
            base = self._sympify(formula)

        elif isinstance(formula, Mapping):
            # keys are "base" expr, "pieces" with list of (expr, where) pairs
            base = self._sympify(formula.get('base', 1))
            for piece in formula.get('pieces', []):
                expr = piece['expr']
                cond = piece['where']
                expressions.append((self._sympify(expr), self._sympify(cond)))

        else:
            raise ValueError('Improper input for formula: {}'.format(type(formula)))

        self.logger.debug('Parsed (expr, cond): {}'.format(expressions))
        return base, expressions

    def _sympify(self, formula):
        """
        Run the given formula expression through :func:`~sympy.core.sympify.sympify` using the
        :attr:`._sympy_ns` namespace.

        Args:
            formula (str): the expression as str

        Returns:
            expr (:class:`sympy.core.expr.Expr`): the symbolic expression

        Raises:
            ValueError: if ``sympify(formula, locals=self._sympy_ns)`` fails

        """
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
            expr (:class:`~sympy.core.expr.Expr`): The sympy expression
            condition (int, :class:`~sympy.core.expr.Expr`): The condition where the expression is
                active

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
        """
        Returns:
            set: atoms in :meth:`.expr` which are of type :class:`~sympy.core.symbol.Symbol`
        """
        return {_ for _ in self.expr().atoms() if isinstance(_, sp.Symbol)}

    def expr(self):
        """
        Evaluate the symbolic expression

        Returns:
            :class:`~sympy.core.expr.Expr`: full expression including piece-wise definitions

        """
        pieces = sum(e * c for e, c in self._pieces)
        if pieces:
            return self.base * pieces
        else:
            return self.base

    def diff(self, *args):
        """
        Compute the differentiation of :meth:`.expr` as symbolic expression

        Args:
            *args: input to :func:`~sympy.core.function.diff`

        Returns:
            :class:`~sympy.core.expr.Expr`: full expression including piece-wise definitions

        """
        if self._pieces:
            ret = sum((self.base * e).diff(*args) * c for e, c in self._pieces)
        else:
            ret = self.base.diff(*args)
        return ret

    __call__ = expr
