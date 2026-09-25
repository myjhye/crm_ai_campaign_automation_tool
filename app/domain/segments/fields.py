"""Public field registry: no contact or arbitrary SQL fields."""
NUMERIC = ['EQ', 'NEQ', 'GT', 'GTE', 'LT', 'LTE', 'BETWEEN', 'IN', 'NOT_IN', 'IS_NULL', 'IS_NOT_NULL']
TEXT = ['EQ', 'NEQ', 'IN', 'NOT_IN', 'IS_NULL', 'IS_NOT_NULL']
FIELDS = {
    'days_since_signup': {'label': '가입 후 경과일', 'type': 'integer', 'comparisons': NUMERIC},
    'cart_events': {'label': '장바구니 이벤트 수', 'type': 'integer', 'comparisons': NUMERIC},
    'purchase_events': {'label': '구매 이벤트 수', 'type': 'integer', 'comparisons': NUMERIC},
    'mobile_landing_events': {'label': '모바일 랜딩 방문 수', 'type': 'integer', 'comparisons': NUMERIC},
    'days_since_last_purchase': {'label': '마지막 구매 후 경과일', 'type': 'integer', 'comparisons': NUMERIC},
    'total_purchase_amount': {'label': '누적 구매액', 'type': 'money', 'comparisons': NUMERIC},
    'order_count': {'label': '완료 주문 수', 'type': 'integer', 'comparisons': NUMERIC},
    'status': {'label': '고객 상태', 'type': 'status', 'comparisons': TEXT},
    'email_consent': {'label': '이메일 수신 동의', 'type': 'boolean', 'comparisons': ['EQ', 'NEQ']},
    'email_opens_30d': {'label': '최근 30일 이메일 오픈 수', 'type': 'integer', 'comparisons': NUMERIC},
    'preferred_category': {'label': '선호 카테고리', 'type': 'text', 'comparisons': TEXT},
}


from datetime import timedelta
from sqlalchemy import select, func, literal
from app.models.customers import CustomerChannel, CustomerEvent, Order, OrderItem, Product


def expressions(snapshot, dataset_id, reference):
    def event_count(kind, mobile=False):
        query = select(func.count()).select_from(CustomerEvent).where(
            CustomerEvent.dataset_id == dataset_id, CustomerEvent.customer_id == snapshot.c.id,
            CustomerEvent.event_at < reference, CustomerEvent.event_type == kind)
        if mobile:
            query = query.where(CustomerEvent.properties['device_type'].astext == 'mobile')
        return query.correlate(snapshot).scalar_subquery()
    email = select(CustomerChannel.consent).where(CustomerChannel.dataset_id == dataset_id, CustomerChannel.customer_id == snapshot.c.id, CustomerChannel.channel == 'EMAIL').correlate(snapshot).scalar_subquery()
    opens = select(func.count()).select_from(CustomerEvent).where(CustomerEvent.dataset_id == dataset_id, CustomerEvent.customer_id == snapshot.c.id, CustomerEvent.event_type == 'EMAIL_OPEN', CustomerEvent.event_at >= reference - timedelta(days=30), CustomerEvent.event_at < reference).correlate(snapshot).scalar_subquery()
    category = select(Product.category).select_from(Order).join(OrderItem, OrderItem.order_id == Order.id).join(Product, Product.id == OrderItem.product_id).where(Order.dataset_id == dataset_id, Order.customer_id == snapshot.c.id, Order.source == 'UPLOADED', Order.status == 'COMPLETED', Order.purchased_at < reference).group_by(Product.category).order_by(func.sum(OrderItem.amount).desc(), Product.category).limit(1).correlate(snapshot).scalar_subquery()
    return {'days_since_signup': func.floor(func.extract('epoch', literal(reference) - snapshot.c.signup_at) / 86400),
            'cart_events': event_count('CART'), 'purchase_events': event_count('PURCHASE'),
            'mobile_landing_events': event_count('LANDING_VIEW', mobile=True),
            'days_since_last_purchase': func.floor(func.extract('epoch', literal(reference) - snapshot.c.last_purchase_at) / 86400),
            'total_purchase_amount': snapshot.c.total_purchase_amount, 'order_count': snapshot.c.order_count, 'status': snapshot.c.status,
            'email_consent': func.coalesce(email, False), 'email_opens_30d': opens, 'preferred_category': category}

