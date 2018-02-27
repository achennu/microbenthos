import logging
from collections import Mapping

import sympy as sp
from fipy.tools import numerix as np

from .expression import Expression
from ..core import DomainEntity


class Process(DomainEntity):
    """
    Class to represent a reaction occurring in the model domain. It is used as an adapter to
    interface the pure mathematical formulation in :class:`Expression` into the model equation
    terms. Additionally, it responds to the simulation clock.
    """
    _lambdify_modules = (np, 'numpy')

    def __init__(self, expr,
                 params = None,
                 implicit = False,
                 **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(Process, self).__init__(**kwargs)



        self.expr = expr
        assert isinstance(self.expr, Expression)

        params = params or {}
        self.params = dict(params)
        self.logger.debug('{}: stored params: {}'.format(self, self.params))

        self.implicit = implicit

    @property
    def expr(self):
        return self._expr

    @expr.setter
    def expr(self, e):
        if isinstance(e, Mapping):
            self.logger.debug('Creating expression instance from dict: {}'.format(e))
            e = Expression(**e)

        if not isinstance(e, Expression):
            raise ValueError('Need an Expression but got {}'.format(type(e)))

        self._expr = e


    def evaluate(self, expr, params = None, domain = None):
        """
        Evaluate the given expression on the supplied domain and param containers.

        If `domain` is not given, then the :attr:`.domain` is used. If `params` is not given,
        then the :attr:`params` dict is used.

        The `expr` atoms are inspected, and all symbols collected. Symbols that are not found in
        the `params` container, are set as variables to be sourced from the `domain` container.

        Args:
            expr (:class:`sp.Expr`): The expression to evaluate
            params (dict, None): The parameter container
            domain (dict, None): The domain container for variables

        Returns:
            The evaluated expression. This is typically an array or fipy binOp term

        """
        self.logger.debug('Evaluating expr {}'.format(expr))

        if not domain:
            self.check_domain()
            domain = self.domain

        if not params:
            params = self.params

        expr_symbols = filter(lambda a: isinstance(a, sp.Symbol), expr.atoms())
        param_symbols = tuple(sp.symbols(params.keys()))
        var_symbols = tuple(set(expr_symbols).difference(set(param_symbols)))
        self.logger.debug('Params available: {}'.format(param_symbols))
        self.logger.debug('Vars to come from domain: {}'.format(var_symbols))
        allsymbs = tuple(var_symbols + param_symbols)

        args = []
        for symbol in allsymbs:
            name_ = str(symbol)
            if symbol in var_symbols:
                args.append(domain[name_])
            elif symbol in param_symbols:
                param = params[name_]
                if hasattr(param, 'unit'):
                    # convert fipy.PhysicalField to base units
                    param = param.inBaseUnits()

                args.append(param)

            else:
                raise RuntimeError('Unknown symbol {!r} in args list'.format(symbol))

        self.logger.debug('Lambdifying with args: {}'.format(allsymbs))
        expr_func = sp.lambdify(allsymbs, expr, modules=self._lambdify_modules)

        self.logger.debug('Evaluating with {}'.format(zip(allsymbs, args)))
        return expr_func(*args)

    def as_source_for(self, varname, **kwargs):
        """
        Cast the underlying :class:`Expression` as a source term for the given variable name.

        If :attr:`.implicit` is True, then the expression will be differentiated (symbolically)
        with respect to variable `v` (from `varname`), and the source expression `S` will be
        attempted to be split as `S1 = dS/dv` and `S0 = S - S1 * v`. If :attr:`.implicit` is
        False, then returns `(S,0)`. This also turns out to be the case when the expression `S`
        is linear with respect to the variable `v`. Finally `S0` and `S1` are evaluated and
        returned.

        Args:
            varname (str): The variable that the expression is a source for
            coeff (int, float): Multiplier for the terms
            kwargs (dict): Keyword arguments forwarded to :meth:`.evaluate`

        Returns:
            tuple: A `(varobj, S0, S1)` tuple, where `varobj` is the variable evaluated on the
            domain, and `S0` and `S1` are the evaluated source expressions on the domain. If `S1`
            is non-zero, then it indicates it should be cast as an implicit source.

        """
        self.logger.debug('{}: creating as source for variable {!r}'.format(self, varname))

        var = sp.symbols(varname)

        if var not in self.expr.symbols():
            S0 = self.expr.expr()
            S1 = 0
            varobj = None

        else:
            S = self.expr.expr()
            varobj = self.evaluate(var, **kwargs)

            if self.implicit:
                S1 = self.expr.diff(var)
                S0 = S - S1 * var

                if var in S1.atoms():
                    self.logger.debug('S1 dependent on {}, so should be implicit term'.format(var))

                else:
                    S0 = S
                    S1 = 0

            else:
                S0 = S
                S1 = 0

        self.logger.debug('Source S0={}'.format(S0))
        self.logger.debug('Source S1={}'.format(S1))

        self.logger.debug('Evaluating S0 and S1 now')
        S0term = self.evaluate(S0, **kwargs)
        if S1:
            S1term = self.evaluate(S1, **kwargs)
        else:
            S1term = 0

        return (varobj, S0term, S1term)

    def as_term(self, **kwargs):
        return self.evaluate(self.expr.expr(), **kwargs)

    def repr_pretty(self):
        e = self.expr.expr()
        return sp.pretty(e)
