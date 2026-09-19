from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.domain.segments.fields import FIELDS


class Condition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operator: Literal['AND', 'OR'] | None = None
    conditions: list['Condition'] | None = Field(default=None, max_length=20)
    field: str | None = None
    comparison: str | None = None
    value: Any = None

    @model_validator(mode='after')
    def validate_node(self):
        if self.operator is not None:
            if not self.conditions or self.model_fields_set & {'field', 'comparison', 'value'}:
                raise ValueError('Group requires children only')
            return self
        if self.conditions is not None or self.field is None or self.comparison is None:
            raise ValueError('Condition requires field and comparison')
        if self.field == 'marketing_consent':
            self.field = 'email_consent'
        spec = FIELDS.get(self.field)
        if spec is None or self.comparison not in spec['comparisons']:
            raise ValueError('Unsupported field or comparison')
        if self.comparison in ('IS_NULL', 'IS_NOT_NULL'):
            if 'value' in self.model_fields_set:
                raise ValueError('Null checks must omit value')
            return self
        def scalar(value):
            kind = spec['type']
            if kind == 'integer':
                if type(value) is not int or not 0 <= value <= 10**12:
                    raise ValueError('Nonnegative integer required')
            elif kind == 'money':
                if not isinstance(value, str) or len(value) > 30:
                    raise ValueError('Money must be a decimal string')
                try:
                    number = Decimal(value)
                except InvalidOperation:
                    raise ValueError('Invalid decimal')
                if not number.is_finite() or not 0 <= number < 10**16 or number.as_tuple().exponent < -2:
                    raise ValueError('Invalid amount')
                return format(number.quantize(Decimal('0.01')), 'f')
            elif kind == 'boolean':
                if type(value) is not bool: raise ValueError('Boolean required')
            elif kind == 'status':
                if value not in ('ACTIVE', 'CHURN_RISK', 'DORMANT', 'WITHDRAWN'): raise ValueError('Invalid status')
            elif not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError('Nonempty string required')
            return value
        if self.comparison in ('IN', 'NOT_IN', 'BETWEEN'):
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 100:
                raise ValueError('Expected 1 to 100 values')
            self.value = [scalar(value) for value in self.value]
            if self.comparison == 'BETWEEN':
                values = [Decimal(value) for value in self.value]
                if len(values) != 2 or values[0] > values[1]: raise ValueError('BETWEEN needs two ascending values')
        else:
            self.value = scalar(self.value)
        return self

    def canonical(self):
        if self.operator:
            return {'operator': self.operator, 'conditions': [node.canonical() for node in self.conditions]}
        result = {'field': self.field, 'comparison': self.comparison}
        if self.comparison not in ('IS_NULL', 'IS_NOT_NULL'): result['value'] = self.value
        return result


def check_limits(node, depth=1):
    if depth > 3: raise ValueError('Maximum group depth is 3')
    count = sum(check_limits(child, depth + bool(child.operator)) for child in node.conditions) if node.operator else 1
    if count > 20: raise ValueError('Maximum 20 conditions')
    return count
