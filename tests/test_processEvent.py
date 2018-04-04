import mock
import pytest
from fipy import PhysicalField, Variable

from microbenthos import Process, ProcessEvent, Expression
from microbenthos.model import MicroBenthosModel


class TestProcessEvent:
    def test_init(self):
        with pytest.raises(TypeError):
            ProcessEvent()

        with pytest.raises(ValueError):
            ProcessEvent(None)

    def test_expr_instance(self):
        exprMock = mock.MagicMock(Expression)

        pe = ProcessEvent(exprMock)
        assert pe.expr is exprMock

    def test_expr_dict(self):
        formula = 'a<b'
        edict = dict(formula=formula)
        pe = ProcessEvent(edict)
        assert pe.expr
        assert pe.expr.expr() == Expression(formula).expr()

    def test_setup(self):
        proc = mock.MagicMock(spec=Process)
        proc.name = mock.Mock(return_value='Proc')
        proc.evaluate.return_value = CONDITION = object()

        model = mock.MagicMock(MicroBenthosModel)
        CLOCK_VAL = Variable(2.5, 'h')
        model.clock = mock.Mock(return_value=CLOCK_VAL)
        model.clock.copy.return_value = CLOCK_VAL

        expr = mock.MagicMock(Expression)
        expr.expr.return_value = EXPR = object()

        pe = ProcessEvent(expr)
        pe.setup(process=proc, model=model)

        assert pe.process == proc
        model.domain.create_var.assert_called_once_with(
            name=repr(pe),
            store=False,
            unit='s',
            value=model.clock
            )
        assert isinstance(pe._prev_clock, Variable)
        expr.expr.assert_called_once()

        proc.evaluate.assert_called_once_with(EXPR)
        assert pe.condition is CONDITION

    def test_on_time_updated(self):

        expr = mock.MagicMock(Expression)
        expr.expr.return_value = EXPR = object()

        pe = ProcessEvent(expr)

        CONDVAL = mock.MagicMock()
        pe.condition = mock.Mock(return_value=CONDVAL)
        CONDVAL.__invert__.return_value = NEG = object()

        PREVVAL = PhysicalField(2, 's')
        pe._prev_clock = PREV = mock.MagicMock(return_value=PREVVAL)
        clock = mock.MagicMock()
        DIFF_VAL = PhysicalField(5, 's')
        clock.__sub__ = mock.Mock(return_value=DIFF_VAL)

        EVENTVAL = PhysicalField(9, 's')
        pe.event_time = mock.MagicMock(return_value=EVENTVAL)
        pe.event_time.value = mock.MagicMock()
        pe.event_time.__iter__.return_value = [1, 2]

        pe.on_time_updated(clock)

        clock.copy().__sub__.assert_called_once()
        pe.condition.assert_called_once()
        pe.event_time.setValue.assert_called_once()

        CONDVAL.__invert__.assert_called_once()

        pe.event_time.value.__setitem__.assert_called_once_with(
            NEG, 0.0)

