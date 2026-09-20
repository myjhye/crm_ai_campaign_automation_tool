"""Set-based PostgreSQL analytics; source orders, not cached customer totals."""
from datetime import timedelta
from sqlalchemy import select, func, case, and_, or_, literal
from app.models.customers import Customer, CustomerChannel, Order, OrderItem, Product, CustomerEvent


def customer_snapshot(dataset_id, reference):
    orders = select(Order.customer_id, func.count().label("order_count"), func.sum(Order.amount).label("amount"),
                    func.max(Order.purchased_at).label("last_purchase_at")).where(
        Order.dataset_id == dataset_id, Order.source == 'UPLOADED', Order.status == "COMPLETED", Order.purchased_at < reference).group_by(Order.customer_id).cte("historical_orders")
    last = func.coalesce(orders.c.last_purchase_at, Customer.signup_at)
    status = case((and_(Customer.withdrawn_at.is_not(None), Customer.withdrawn_at <= reference), "WITHDRAWN"),
                  (last <= reference - timedelta(days=60), "DORMANT"),
                  (last <= reference - timedelta(days=30), "CHURN_RISK"), else_="ACTIVE")
    return select(Customer.id, Customer.external_id, Customer.name, Customer.signup_at, status.label("status"),
                  func.coalesce(orders.c.order_count, 0).label("order_count"),
                  func.coalesce(orders.c.amount, 0).label("total_purchase_amount"), orders.c.last_purchase_at).outerjoin(
        orders, Customer.id == orders.c.customer_id).where(Customer.dataset_id == dataset_id, Customer.signup_at < reference).cte("customer_snapshot")


def period_orders(dataset_id, start, end):
    return select(Order.customer_id, func.count().label("count")).where(Order.dataset_id == dataset_id,
        Order.source == 'UPLOADED', Order.status == "COMPLETED", Order.purchased_at >= start, Order.purchased_at < end).group_by(Order.customer_id).cte("period_orders")


def event_customers(dataset_id, start, end, kinds):
    return select(CustomerEvent.customer_id).where(CustomerEvent.dataset_id == dataset_id,
        CustomerEvent.event_at >= start, CustomerEvent.event_at < end, CustomerEvent.event_type.in_(kinds)).distinct()


def funnel_sets(dataset_id, start, end):
    def scope(kind):
        return (CustomerEvent.dataset_id == dataset_id, CustomerEvent.event_type == kind,
                CustomerEvent.event_at >= start, CustomerEvent.event_at < end)
    views = select(CustomerEvent.customer_id, func.min(CustomerEvent.event_at).label("at")).where(*scope("VIEW")).group_by(CustomerEvent.customer_id).cte("first_view")
    carts = select(CustomerEvent.customer_id, func.min(CustomerEvent.event_at).label("at")).join(views,
        and_(views.c.customer_id == CustomerEvent.customer_id, CustomerEvent.event_at > views.c.at)).where(*scope("CART")).group_by(CustomerEvent.customer_id).cte("first_cart_after_view")
    purchases = select(CustomerEvent.customer_id).join(carts,
        and_(carts.c.customer_id == CustomerEvent.customer_id, CustomerEvent.event_at > carts.c.at)).where(*scope("PURCHASE")).distinct().cte("purchase_after_cart")
    return views, carts, purchases


def cohort_condition(snapshot, query):
    if query.cohort == "new": return snapshot.c.signup_at >= query.start
    if query.cohort == "active": return snapshot.c.id.in_(event_customers(query.dataset_id, query.start, query.end, ["VIEW", "CART", "PURCHASE"]))
    if query.cohort in ("purchased", "repeat"):
        orders = period_orders(query.dataset_id, query.start, query.end)
        return snapshot.c.id.in_(select(orders.c.customer_id).where(orders.c.count >= (2 if query.cohort == "repeat" else 1)))
    if query.cohort in ("view", "cart", "purchase"):
        group = funnel_sets(query.dataset_id, query.start, query.end)[["view", "cart", "purchase"].index(query.cohort)]
        return snapshot.c.id.in_(select(group.c.customer_id))
    return literal(True)


def list_customers(session, query):
    snapshot = customer_snapshot(query.dataset_id, query.end)
    criteria = [cohort_condition(snapshot, query)]
    if query.status: criteria.append(snapshot.c.status == query.status)
    if query.signup_from: criteria.append(snapshot.c.signup_at >= query.signup_from)
    if query.signup_to: criteria.append(snapshot.c.signup_at < query.signup_to)
    if query.q:
        search = query.q.lower()
        email_match = select(CustomerChannel.customer_id).where(CustomerChannel.dataset_id == query.dataset_id,
            CustomerChannel.channel == "EMAIL", func.lower(CustomerChannel.contact).contains(search, autoescape=True))
        criteria.append(or_(func.lower(snapshot.c.name).contains(search, autoescape=True),
            func.lower(snapshot.c.external_id).contains(search, autoescape=True), snapshot.c.id.in_(email_match)))
    total = session.scalar(select(func.count()).select_from(snapshot).where(*criteria))
    sort = snapshot.c[query.sort]
    sort = sort.asc().nulls_last() if query.direction == "asc" else sort.desc().nulls_last()
    rows = session.execute(select(snapshot).where(*criteria).order_by(sort, snapshot.c.id).offset(query.offset).limit(query.page_size)).mappings().all()
    return rows, total


def get_customer(session, dataset_id, customer_id, reference):
    snapshot = customer_snapshot(dataset_id, reference)
    return session.execute(select(snapshot).where(snapshot.c.id == customer_id)).mappings().first()


def channels(session, dataset_id, customer_ids):
    return session.scalars(select(CustomerChannel).where(CustomerChannel.dataset_id == dataset_id,
        CustomerChannel.customer_id.in_(customer_ids))).all() if customer_ids else []


def preferred_category(session, dataset_id, customer_id, reference):
    return session.execute(select(Product.category, func.sum(OrderItem.amount).label("amount")).select_from(OrderItem).join(
        Order, and_(Order.id == OrderItem.order_id, Order.dataset_id == OrderItem.dataset_id)).join(
        Product, and_(Product.id == OrderItem.product_id, Product.dataset_id == OrderItem.dataset_id)).where(
        OrderItem.dataset_id == dataset_id, Order.customer_id == customer_id, Order.source == 'UPLOADED', Order.status == "COMPLETED",
        Order.purchased_at < reference).group_by(Product.category).order_by(func.sum(OrderItem.amount).desc(), Product.category).limit(1)).first()


def events(session, query, customer_id):
    conditions = (CustomerEvent.dataset_id == query.dataset_id, CustomerEvent.customer_id == customer_id,
                  CustomerEvent.event_at >= query.start, CustomerEvent.event_at < query.end)
    total = session.scalar(select(func.count()).select_from(CustomerEvent).where(*conditions))
    rows = session.execute(select(CustomerEvent.id, CustomerEvent.event_type, CustomerEvent.event_at,
        CustomerEvent.created_at, CustomerEvent.order_id).where(*conditions).order_by(CustomerEvent.event_at.desc(), CustomerEvent.id).offset(query.offset).limit(query.page_size)).mappings().all()
    return rows, total


def period_metrics(session, dataset_id, start, end):
    customers = customer_snapshot(dataset_id, end)
    orders = period_orders(dataset_id, start, end)
    active = event_customers(dataset_id, start, end, ["VIEW", "CART", "PURCHASE"]).cte("active_customers")
    active_condition = customers.c.id.in_(select(active.c.customer_id))
    result = session.execute(select(
        func.count().label("total_customers"),
        func.count().filter(customers.c.signup_at >= start).label("new_customers"),
        func.count().filter(customers.c.status == "DORMANT").label("dormant_customers"),
        func.count().filter(active_condition).label("active_customers"),
        func.count().filter(orders.c.count >= 1).label("buyers"),
        func.count().filter(orders.c.count >= 2).label("repeat_buyers"),
        func.count().filter(and_(active_condition, orders.c.count >= 1)).label("active_buyers"),
    ).select_from(customers.outerjoin(orders, customers.c.id == orders.c.customer_id))).mappings().one()
    return dict(result)


def status_distribution(session, dataset_id, reference):
    snapshot = customer_snapshot(dataset_id, reference)
    return dict(session.execute(select(snapshot.c.status, func.count()).group_by(snapshot.c.status)).all())


def funnel_counts(session, dataset_id, start, end):
    groups = funnel_sets(dataset_id, start, end)
    return list(session.execute(select(*(select(func.count()).select_from(group).scalar_subquery() for group in groups))).one())
