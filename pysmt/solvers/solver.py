#
# This file is part of pySMT.
#
#   Copyright 2014 Andrea Micheli and Marco Gario
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
import pysmt.shortcuts
from pysmt.typing import BOOL
from pysmt.exceptions import SolverReturnedUnknownResultError
from six.moves import xrange


class Solver(object):
    """Represents a generic SMT Solver."""

    # Define the supported logics for the Solver
    LOGICS = []

    def __init__(self, environment, logic, user_options=None):
        if logic is None:
            raise ValueError("Cannot provide 'None' as logic")

        self.environment = environment
        self.pending_pop = False
        self.logic = logic
        self.options = self.get_default_options(logic, user_options)
        self._destroyed = False
        return

    def get_default_options(self, logic=None, user_options=None):
        res = SolverOptions()
        if user_options is not None:
            for k in ["generate_models", "unsat_cores_mode"]:
                if k in user_options:
                    setattr(res, k, user_options[k])
        return res

    def is_sat(self, formula):
        """Checks satisfiability of the formula w.r.t. the current state of
        the solver.

        Previous assertions are taken into account.

        :type formula: FNode
        :returns: Whether formula is satisfiable
        :rtype: bool
        """
        assert formula in self.environment.formula_manager, \
               "Formula does not belong to the current Formula Manager"

        use_solving_under_assumption = False
        try:
            self.push()
        except NotImplementedError:
            use_solving_under_assumption = True

        if use_solving_under_assumption:
            res = self.solve([formula])
        else:
            self.add_assertion(formula)
            res = self.solve()
            self.pending_pop = True
        return res

    def is_valid(self, formula):
        """Checks validity of the formula w.r.t. the current state of the
        solver.

        Previous assertions are taken into account. See :py:func:`is_sat`

        :type formula: FNode
        :returns: Whether formula is valid
        :rtype: bool
        """
        Not = self.environment.formula_manager.Not
        return not self.is_sat(Not(formula))

    def is_unsat(self, formula):
        """Checks unsatisfiability of the formula w.r.t. the current state of
        the solver.

        Previous assertions are taken into account. See :py:func:`is_sat`

        :type formula: FNode
        :returns: Whether formula is unsatisfiable
        :rtype: bool
        """
        return not self.is_sat(formula)

    def get_values(self, exprs):
        """Returns the value of the expressions if a model was found.

        Restrictions: Requires option :produce-models to be set to true and can
                      be called only after check-sat returned sat or unknown,
                      if no change to the assertion set occurred.

        :type exprs: List of FNodes
        :returns: A dictionary associating to each expr a value
        :rtype: dict
        """
        res = {}
        for f in exprs:
            v = self.get_value(f)
            res[f] = v
        return res

    def push(self, levels=1):
        """Push the current context of the given number of levels.

        :type levels: int
        """
        raise NotImplementedError

    def pop(self, levels=1):
        """Pop the context of the given number of levels.

        :type levels: int
        """
        raise NotImplementedError

    def exit(self):
        """Exits from the solver and closes associated resources."""
        if not self._destroyed:
            self._exit()
            self._destroyed = True

    def _exit(self):
        """Exits from the solver and closes associated resources."""
        raise NotImplementedError

    def reset_assertions(self):
        """Removes all defined assertions."""
        raise NotImplementedError

    def declare_variable(self, var):
        """Declare a variable in the solver.

        :type var: FNode
        """
        raise NotImplementedError

    def add_assertion(self, formula, named=None):
        """Add assertion to the solver.

        This is a wrapper to :py:func:`assert_`, for better naming.
        """
        raise NotImplementedError


    def solve(self, assumptions=None):
        """Returns the satisfiability value of the asserted formulas.

        Assumptions is a list of Boolean variables or negations of
        boolean variables. If assumptions is specified, the
        satisfiability result is computed assuming that all the
        specified literals are True.

        A call to solve([a1, ..., an]) is functionally equivalent to:

        push()
        add_assertion(And(a1, ..., an))
        res = solve()
        pop()
        return res

        but is in general more efficient.
        """
        raise NotImplementedError

    def print_model(self, name_filter=None):
        """Prints the model (if one exists).

        An optional function can be passed, that will be called on each symbol
        to decide whether to print it.
        """
        raise NotImplementedError

    def get_value(self, formula):
        """Returns the value of formula in the current model (if one exists).

        This is a simplified version of the SMT-LIB function get_values
        """
        raise NotImplementedError

    def get_py_value(self, formula):
        """Returns the value of formula as a python type.

        E.g., Bool(True) is translated into True.
        This simplifies writing code that branches on values in the model.
        """
        res = self.get_value(formula)
        assert res.is_constant()
        return res.constant_value()

    def get_py_values(self, formulae):
        """Returns the values of the formulae as python types.

        Returns a dictionary mapping each formula to its python value.
        """
        res = {}
        for f in formulae:
            v = self.get_py_value(f)
            res[f] = v
        return res

    def get_model(self):
        """Returns an instance of Model that survives the solver instance."""
        raise NotImplementedError

    def set_options(self, options):
        """Sets multiple options at once.

        :param options: Options to be set
        :type options: Dictionary
        """
        raise NotImplementedError

    def __enter__(self):
        """Manages entering a Context (i.e., with statement)"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Manages exiting from Context (i.e., with statement)

        The default behaviour is "close" the solver by calling the
        py:func:`exit` method.
        """
        self.exit()

    def _assert_no_function_type(self, item):
        """Enforces that argument 'item' cannot be a FunctionType.

        Raises TypeError.
        """
        if item.is_symbol() and item.symbol_type().is_function_type():
            raise TypeError("Cannot call get_value() on a FunctionType")

    def _assert_is_boolean(self, formula):
        """Enforces that argument 'formula' is of type Boolean.

        Raises TypeError.
        """
        t = pysmt.shortcuts.get_type(formula)
        if t != BOOL:
            raise TypeError("Argument must be boolean.")


class IncrementalTrackingSolver(Solver):
    """A solver that keeps track of the asserted formulae

    This class provides tracking of the assertions that are stored
    inside the solver, the last executed command and the last solving
    result.

    It requires the extending class to implement the following proxy
    methods:

    * _reset_assertions
    * _add_assertion
    * _solve
    * _push
    * _pop

    The semantics of each function is the same as the non-proxy
    version except for _add_assertion that is supposed to return a
    result (of any type) that will constitute the elements of the
    self.assertions list.
    """

    def __init__(self, environment, logic, user_options=None):
        """See py:func:`Solver.__init__()`."""
        Solver.__init__(self, environment, logic, user_options=user_options)

        self._last_result = None
        self._last_command = None

        self._assertion_stack = []
        self._backtrack_points = []

    @property
    def last_command(self):
        """Returns the name of the laste executed command"""
        return self._last_command

    @property
    def last_result(self):
        """Returns the result of the last call to solve().

        Returns True, False or "unknown": the last result of the last
        call to solve(). If solve has never been called, None is
        returned
        """
        return self._last_result

    @property
    def assertions(self):
        """Returns the list of assertions that are still in the solver.

        Returns the list of results of calls to _add_assertion() that
        are still asserted in the solver
        """
        return self._assertion_stack

    def _reset_assertions(self):
        raise NotImplementedError

    def reset_assertions(self):
        self._reset_assertions()
        self._last_command = "reset_assertions"

    def _add_assertion(self, formula, named=None):
        raise NotImplementedError

    def add_assertion(self, formula, named=None):
        tracked = self._add_assertion(formula, named=named)
        self._assertion_stack.append(tracked)
        self._last_command = "assert"

    def _solve(self, assumptions=None):
        raise NotImplementedError

    def solve(self, assumptions=None):
        try:
            res = self._solve(assumptions=assumptions)
            self._last_result = res
            return res
        except SolverReturnedUnknownResultError:
            self._last_result = "unknown"
            raise

        finally:
            self._last_command = "solve"

    def _push(self, levels=1):
        raise NotImplementedError

    def push(self, levels=1):
        self._push(levels=levels)
        point = len(self._assertion_stack)
        for _ in xrange(levels):
            self._backtrack_points.append(point)
        self._last_command = "push"

    def _pop(self, levels=1):
        raise NotImplementedError

    def pop(self, levels=1):
        self._pop(levels=levels)
        for _ in xrange(levels):
            point = self._backtrack_points.pop()
            self._assertion_stack = self._assertion_stack[0:point]
        self._last_command = "pop"


class UnsatCoreSolver(object):
    """A solver supporting unsat core extraction"""

    UNSAT_CORE_SUPPORT = True

    def get_unsat_core(self):
        """Returns the unsat core as a set of formulae.

        After a call to solve() yielding UNSAT, returns the unsat core
        as a set of formulae
        """
        raise NotImplementedError


    def get_named_unsat_core(self):
        """Returns the unsat core as a dict of names to formulae.

        After a call to solve() yielding UNSAT, returns the unsat core as a
        dict of names to formulae
        """
        raise NotImplementedError


class Model(object):
    """An abstract Model for a Solver.

    This class provides basic services to operate on a model returned
    by a solver. This class is used as superclass for more specific
    Models, that are solver dependent or by the EagerModel class.
    """

    def __init__(self, environment):
        self.environment = environment
        self._converter = None

    def get_value(self, formula, model_completion=True):
        """Returns the value of formula in the current model (if one exists).

        If model_completion is True, then variables not appearing in the
        assignment are given a default value, otherwise an error is generated.

        This is a simplified version of the SMT-LIB funtion get_values .
        """
        raise NotImplementedError

    def get_values(self, formulae, model_completion=True):
        """Evaluates the values of the formulae in the current model.

        Evaluates the values of the formulae in the current model
        returning a dictionary.
        """
        res = {}
        for f in formulae:
            v = self.get_value(f, model_completion=model_completion)
            res[f] = v
        return res

    def get_py_value(self, formula, model_completion=True):
        """Returns the value of formula as a python type.

        E.g., Bool(True) is translated into True.
        This simplifies writing code that branches on values in the model.
        """
        res = self.get_value(formula, model_completion=model_completion)
        assert res.is_constant()
        return res.constant_value()

    def get_py_values(self, formulae, model_completion=True):
        """Returns the values of the formulae as python types.

        Returns the values of the formulae as python types. in the
        current model returning a dictionary.
        """
        res = {}
        for f in formulae:
            v = self.get_py_value(f, model_completion=model_completion)
            res[f] = v
        return res

    @property
    def converter(self):
        """Get the Converter associated with the Solver."""
        return self._converter

    @converter.setter
    def converter(self, value):
        self._converter = value

    def __getitem__(self, idx):
        return self.get_value(idx, model_completion=True)

    def __str__(self):
        return "\n".join([ "%s := %s" % (var, value) for (var, value) in self])


class Converter(object):
    """A Converter implements functionalities to convert expressions.

    There are two key methods: convert() and back().
    The first performs the forward conversion (pySMT -> Solver API),
    the second performs the backwards conversion (Solver API -> pySMT)
    """

    def convert(self, formula):
        """Convert a PySMT formula into a Solver term."""
        raise NotImplementedError

    def back(self, expr):
        """Convert an expression of the Solver into a PySMT term."""
        raise NotImplementedError


class SolverOptions(object):
    """Abstract class to represent Solver Options."""
    def __init__(self, generate_models=True, unsat_cores_mode=None):
        self.generate_models = generate_models
        self.unsat_cores_mode = unsat_cores_mode
