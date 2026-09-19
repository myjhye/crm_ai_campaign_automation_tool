from decimal import Decimal
from sqlalchemy import and_, or_
from app.domain.segments.fields import expressions


def compile_condition(node, fields):
    if node.operator:
        return (and_ if node.operator == 'AND' else or_)(*[compile_condition(child, fields) for child in node.conditions])
    column, value, op = fields[node.field], node.value, node.comparison
    if node.field == 'total_purchase_amount' and value is not None:
        value = [Decimal(v) for v in value] if isinstance(value, list) else Decimal(value)
    if op == 'IS_NULL': return column.is_(None)
    if op == 'IS_NOT_NULL': return column.is_not(None)
    if op == 'IN': return column.in_(value)
    if op == 'NOT_IN': return column.not_in(value)
    if op == 'BETWEEN': return column.between(*value)
    if op == 'EQ': return column == value
    if op == 'NEQ': return column != value
    if op == 'GT': return column > value
    if op == 'GTE': return column >= value
    if op == 'LT': return column < value
    if op == 'LTE': return column <= value
    raise ValueError('Unsupported comparison')
