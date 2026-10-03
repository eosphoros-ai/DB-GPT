from datetime import datetime

import pytest

from dbgpt_serve.agent.app.recommend_question.recommend_question import (
    RecommendQuestion,
)
from dbgpt_serve.agent.db.gpts_app import (
    GptsApp,
    GptsAppDao,
    GptsAppDetail,
    GptsAppEntity,
)


@pytest.mark.parametrize(
    ("model_cls", "timestamp_fields"),
    [
        (GptsApp, ("created_at", "updated_at")),
        (GptsAppDetail, ("created_at", "updated_at")),
        (RecommendQuestion, ("gmt_create", "gmt_modified")),
    ],
)
def test_default_timestamps_are_generated_when_each_model_is_created(
    model_cls, timestamp_fields
):
    creation_started_at = datetime.now()

    model = model_cls()

    creation_finished_at = datetime.now()
    for field_name in timestamp_fields:
        timestamp = getattr(model, field_name)
        assert creation_started_at <= timestamp <= creation_finished_at


def test_app_dao_persists_the_app_creation_timestamp(monkeypatch):
    captured = []

    class RecordingSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def add(self, entity):
            captured.append(entity)

        def add_all(self, entities):
            captured.extend(entities)

    dao = GptsAppDao()
    monkeypatch.setattr(dao, "session", RecordingSession)
    creation_started_at = datetime.now()

    dao.create(GptsApp(details=[]))

    app_entity = next(
        entity for entity in captured if isinstance(entity, GptsAppEntity)
    )
    assert app_entity.created_at >= creation_started_at
