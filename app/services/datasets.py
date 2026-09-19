from sqlalchemy import func

from app.core.errors import AppError
from app.models.datasets import Dataset
from app.repositories import datasets as repository
from app.services import audit


def require_dataset(session, dataset_id, *, lock=False):
    dataset = repository.get(session, dataset_id, lock=lock)
    if dataset is None:
        raise AppError("NOT_FOUND", "데이터셋을 찾을 수 없습니다.", 404)
    return dataset


def create_dataset(session, payload, request_id):
    with session.begin():
        dataset = Dataset(name=payload.name, source="DEMO")
        session.add(dataset)
        session.flush()
        audit.record_change(session, dataset_id=dataset.id, resource_id=dataset.id,
                            actor_type="VISITOR", action="DATASET_CREATED", request_id=request_id,
                            previous_version=None, new_version=dataset.version)
    return dataset


def update_dataset(session, dataset_id, payload, request_id):
    with session.begin():
        dataset = require_dataset(session, dataset_id, lock=True)
        if dataset.version != payload.version:
            raise AppError("VERSION_CONFLICT", "다른 변경이 적용되었습니다. 최신 데이터셋을 다시 불러와주세요.")
        if dataset.name == payload.name:
            return dataset
        previous = dataset.version
        dataset.name = payload.name
        dataset.version += 1
        dataset.updated_at = func.clock_timestamp()
        session.flush()
        audit.record_change(session, dataset_id=dataset.id, resource_id=dataset.id,
                            actor_type="VISITOR", action="DATASET_UPDATED", request_id=request_id,
                            previous_version=previous, new_version=dataset.version)
        session.refresh(dataset)
    return dataset
