import logging
import operator
from abc import ABCMeta, abstractmethod
from collections import Mapping, OrderedDict

from fipy.tools import numerix
from sympy import sympify, symbols, lambdify, Symbol, SympifyError

from .entity import DomainEntity
from ..utils.snapshotters import snapshot_var


class Process(DomainEntity):
    """
    Class to represent a process occurring in the benthic domain.
    """

    __metaclass__ = ABCMeta

    def __init__(self, **kwargs):
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in Process')
        kwargs['logger'] = self.logger
        super(Process, self).__init__(**kwargs)

    @abstractmethod
    def dependent_vars(self):
        raise NotImplementedError

    @abstractmethod
    def add_response(self):
        pass

    @abstractmethod
    def evaluate(self, D, P = None, full = True):
        pass


class ExprProcess(Process):
    """
    Class to represent a process occurring in the benthic domain. This class helps to formulate
    an expression of the relationships between variables as well as update specific features with
    the simulation clock.
    """

    _lambdify_modules = (numerix, 'numpy')
    _sympy_ns = {}

    def __init__(self, formula, varnames, params = None, responses = None, expected_unit = None,
                 implicit_source = False,
                 **kwargs):
        """
        Create a process expressed by the formula, possibly containing subprocesses.

        The scheme of operation involves converting the formula into a symbolic expression (
        using :meth:`sympify`), and symbols for the variables are created from `varnames`. This
        expression, stored in :attr:`expr`, is split into a core expression that is independent
        of the symbols indicating the subprocess. This core expression can be evaluated to
        perform computations by replacement by appropriate values during the evaulation phase.
        This core expression is made into a lambda function, and the expression is rendered into
        a callable function using :meth:`lambdify`. For computation in the model domain,
        the symbols are replaced by domain variables of the same name and parameters from the
        supplied `params` mapping. Any symbols referring to  subprocesses are replaced by the
        result of calling :meth:`.evaluate` on those instances.

        Args:
            formula (str): Valid expression for formula to be used with :meth:`sympify`
            varsnames (list): Names of the variables in the formula
            params (dict): Names and values for parameters in the formula. The names matching the
            symbols in the formula will be replaced during evaluation.
            responses: A mapping of {`name`: `params`} for any subprocesses of this process. The
            `params` must be a dict of the init arguments, for the same class.
            expected_unit (str): The units the evaluation results should be compatible with
            sympy_ns: A namespace dict for sympification (see: :meth:`sympify` arg `locals`)
            **kwargs: passed to superclass
        """
        super(ExprProcess, self).__init__(**kwargs)

        self._formula = None
        self.responses = OrderedDict()
        #: mapping of process name (str) to an instance of the Process

        if params is None:
            params = {}
        if not isinstance(params, Mapping):
            self.logger.warning('Params is not a Mapping, but {}'.format(type(params)))

        # self.params = OrderedDict((symbols(str(k)), v) for (k, v) in params.iteritems())
        # self.params_tuple = tuple(self.params)
        params = OrderedDict(params)
        self.check_names(params)
        self.params = params
        self.logger.debug('Stored params: {}'.format(self.params))

        self.check_names(varnames)
        self.varnames = tuple(varnames)
        self.vars = tuple(symbols([str(_) for _ in self.varnames]))
        self.logger.debug('Created var symbols: {}'.format(self.vars))

        self._formula = formula

        expr = self.parse_formula(formula)
        self.expr = expr

        responses = responses or {}
        self.check_names(responses)
        for k, v in responses.iteritems():
            self.add_response_from(k, **v)

        self.expected_unit = expected_unit

        argsyms = [sympify(_) for _ in self.argnames]
        self.expr_func = self._lambdify(self.expr, argsyms)

        self._evaled_domain = None
        self._evaled_params = None
        self._evaled = None

        self.implicit_source = implicit_source

    def __repr__(self):
        return 'Process[{},{}]:responses[{}]'.format(self.expr, self.vars,
                                                     ','.join(self.responses.keys()))

    def check_names(self, names):
        """
        Checks that the items of the list are sympifyable

        Args:
            names: List of strings

        Returns:
            None

        Raises:
            ValueError if any improper names are found

        """
        improper = []
        for n in names:
            try:
                n_ = sympify(n)
            except:
                self.logger.warning('Name {} not valid expr'.format(n))
                improper.append(n)
        if improper:
            self.logger.error('Names are improper: {}'.format(improper))
            raise ValueError('Improper names found: {}'.format(improper))

    def dependent_vars(self):
        """

        Returns:
            List of variable names that this process (& its subprocesses) depend on

        """
        vars = []
        vars.extend(self.varnames)
        for proc in self.responses.values():
            vars.extend(proc.dependent_vars())
        return set(vars)

    @property
    def formula(self):
        return self._formula

    @property
    def argnames(self):
        return self.varnames + tuple(self.params)

    def parse_formula(self, formula):
        """
        Convert formula into an expression, also populating the responses

        Args:
            formula (str): formula as a string

        Returns:
            Instance of :class:`Expr`

        Raises:
            ValueError if :meth:`sympify` raises an exception
        """
        self.logger.debug('Parsing formula: {formula}'.format(formula=formula))
        self.logger.debug('Sympy namespace: {}'.format(self._sympy_ns))
        try:
            expr = sympify(formula, locals=self._sympy_ns)
            self.logger.debug('Created expression: {}'.format(expr))

        except (SympifyError, SyntaxError):
            self.logger.error('Sympify failed on {}'.format(formula), exc_info=True)
            raise ValueError('Could not parse formula')

        return expr

    def add_response(self, name, process):
        """
        Add a response function to this process

        Args:
            name: Name to refer to the object
            process: The instance of the Process

        Returns:
            None

        """

        self.check_names([name])

        if name in self.responses:
            self.logger.warning('Process {!r} already exists. Over-writing with {}'.format(name,
                                                                                           process))

        self.responses[name] = process
        self.logger.debug('Added response {!r}: {}'.format(name, process))

    def add_response_from(self, name, **params):
        self.logger.debug('Adding response: {}:: {}'.format(name, params))

        response = self.from_params(**params)

        self.add_response(name, response)

    def on_domain_set(self):
        for resp in self.responses.values():
            resp.set_domain(self.domain)

    def _lambdify(self, expr, args):
        """
        Make a lambda function from the expression

        Using :meth:`lambdify`, an :attr:`.exprfunc` function is created, which can be called
        with :attr:`.exprfunc_vars` as `exprfunc(*exprfunc_vars)` to evaluate the expression.
        `exprfunc_vars` also provides the order in which other arrays should be used to replace
        the symbols therein.

        Args:
            expr: if None, then :attr:`self.expr` is used

        Returns:
            exprfunc (lambda): a callable lambda function
            exprfunc_vars (tuple): the order of arguments (as symbols) to call the function with.

        """
        if not expr:
            raise ValueError('No expression to lambdify!')

        eatoms = {_ for _ in expr.atoms() if isinstance(_, Symbol)}
        # a set of the atoms (symbols) in the expr
        # we extract only symbols, and ignore the numbers

        # check that the expression actually only contains these symbols
        mismatched = set(args).difference(eatoms)
        if mismatched:
            self.logger.warning(
                'Expression atoms {} possible mismatch with vars & params {}'.format(eatoms, args))
            # raise ValueError('Expression & var/params mismatch!')

        self.logger.debug('Lambdifying: {} with args {}'.format(expr, args))
        exprfunc = lambdify(args, expr, modules=self._lambdify_modules)
        self.logger.debug('Created exprfunc: {} with args: {}'.format(exprfunc, args))

        return exprfunc

    def evaluate(self, domain = None, params = None, full = True):
        # TODO: Write good docstring here with examples

        if not domain:
            self.check_domain()
            domain = self.domain
        if not params:
            params = self.params

        if (domain is self._evaled_domain) and (params == self._evaled_params) and (
                self._evaled is not None):
            self.logger.debug('Returning cached evaluation in {}'.format(self))
            return self._evaled

        self.logger.debug('Evaluating {!r} on {!r}'.format(self.expr, domain))

        # collect the arguments
        varargs = [domain[_] for _ in self.varnames]
        pargs = [params[_] for _ in self.params]
        from fipy import PhysicalField
        pargs = [_.inBaseUnits() if isinstance(_, PhysicalField) else _ for _ in pargs]

        args = varargs + pargs
        # follow the same order of the params ordered dict

        self.logger.debug('Evaluating {} with args: {}'.format(self.expr, args))
        evaled = self.expr_func(*args)

        resp_evals = []
        if full:
            # evaluate the subprocesses
            for resp_name, response in self.responses.items():
                self.logger.debug('Evaluating response {}'.format(resp_name))
                resp_evals.append(response.evaluate(domain, params.get(resp_name, None)))

        if resp_evals:
            evaled *= reduce(operator.mul, resp_evals)

        self.logger.debug("Caching evaluate results")
        self._evaled = evaled
        self._evaled_domain = domain
        self._evaled_params = params.copy()

        return evaled

    def snapshot(self, base = False):
        """
        Returns a snapshot of the Process's state

        Args:
            base (bool): Convert to base units?

        Returns:
            Dictionary with structure:
                * `metadata`:
                    * `formula`: str(:attr:`.expr`)
                    * `varnames`: :attr:`.varnames`
                    * `params`: (name, val) of :attr:`.params`
                    * `dependent_vars`: :meth:`.dependent_vars()`

                * `data`: (array of :meth:`.evaluate()`, dict(unit=unit)
                * `responses`: snapshot of values in  :attr:`.responses`
        """
        self.check_domain()
        self.logger.debug('Snapshot: {}'.format(self))

        state = dict()
        meta = state['metadata'] = {}
        meta['formula'] = str(self.expr)
        meta['varnames'] = self.varnames
        meta['dependent_vars'] = tuple(self.dependent_vars())
        meta['expected_unit'] = self.expected_unit
        meta['param_names'] = tuple(self.params.keys())

        for p, pval in self.params.items():
            meta[p] = str(pval)

        evaled = self.evaluate()

        if hasattr(evaled, 'unit'):
            state['data'] = snapshot_var(evaled, base=base, to_unit=self.expected_unit)

        else:
            state['data'] = snapshot_var(evaled, base=base)

        responses = state['responses'] = {}
        for resp, respobj in self.responses.items():
            responses[resp] = respobj.snapshot()

        return state
