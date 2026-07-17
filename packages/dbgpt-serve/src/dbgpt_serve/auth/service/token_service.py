"""Idempotent model-call metering and scoped usage queries."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from dbgpt_serve.auth.api.schemas import (
    Page,
    TokenDailyResponse,
    TokenUsageCreate,
    TokenUsageQueryRequest,
    TokenUsageResponse,
    TokenUsageSummaryResponse,
)
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
    TokenDailyEntity,
    TokenUsageDao,
    TokenUsageEntity,
    UserAccountGrantEntity,
)
from dbgpt_serve.auth.service.errors import ManagementValidationError
from dbgpt_serve.auth.service.management import Operator, _utcnow

SHANGHAI = ZoneInfo("Asia/Shanghai")


class TokenService:
    """Store every physical model call and maintain reproducible daily totals."""

    def __init__(self, dao: Optional[TokenUsageDao] = None) -> None:
        self._dao = dao or TokenUsageDao()

    def record_usage(self, usage: TokenUsageCreate) -> bool:
        """Return true only when a new call ID was metered."""
        created_at = self._as_naive_utc(usage.gmt_created)
        stat_date = (
            created_at.replace(tzinfo=timezone.utc).astimezone(SHANGHAI).date()
        ).isoformat()
        for attempt in range(2):
            try:
                with self._dao.session() as session:
                    if (
                        session.query(TokenUsageEntity.id)
                        .filter(TokenUsageEntity.call_id == usage.call_id)
                        .first()
                        is not None
                    ):
                        return False
                    entity_data = usage.model_dump(exclude={"gmt_created"})
                    session.add(
                        TokenUsageEntity(
                            **entity_data,
                            gmt_created=created_at,
                        )
                    )
                    session.flush()
                    account_set_id = usage.account_set_id or ""
                    daily = (
                        session.query(TokenDailyEntity)
                        .filter(
                            TokenDailyEntity.stat_date == stat_date,
                            TokenDailyEntity.user_id == usage.user_id,
                            TokenDailyEntity.role_snapshot == usage.role_snapshot,
                            TokenDailyEntity.account_set_id == account_set_id,
                            TokenDailyEntity.model == usage.model,
                        )
                        .with_for_update()
                        .first()
                    )
                    now = _utcnow()
                    if daily is None:
                        daily = TokenDailyEntity(
                            stat_date=stat_date,
                            user_id=usage.user_id,
                            role_snapshot=usage.role_snapshot,
                            account_set_id=account_set_id,
                            model=usage.model,
                            input_tokens=usage.input_tokens,
                            output_tokens=usage.output_tokens,
                            total_tokens=usage.total_tokens,
                            call_count=1,
                            gmt_created=now,
                            gmt_modified=now,
                        )
                        session.add(daily)
                    else:
                        daily.input_tokens += usage.input_tokens
                        daily.output_tokens += usage.output_tokens
                        daily.total_tokens += usage.total_tokens
                        daily.call_count += 1
                        daily.gmt_modified = now
                    session.flush()
                return True
            except IntegrityError:
                if self._dao.get_by_call_id(usage.call_id) is not None:
                    return False
                if attempt == 1:
                    raise
        return False

    def query_usage(
        self,
        filters: TokenUsageQueryRequest,
        operator: Operator,
        page: int,
        page_size: int,
    ) -> Page[TokenUsageResponse]:
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            query = session.query(TokenUsageEntity)
            query = self._scope_query(query, TokenUsageEntity, session, operator)
            query = self._apply_usage_filters(query, filters)
            total = query.count()
            entities = (
                query.order_by(
                    TokenUsageEntity.gmt_created.desc(), TokenUsageEntity.id.desc()
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [TokenUsageResponse.model_validate(item) for item in entities]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def query_daily(
        self, filters: TokenUsageQueryRequest, operator: Operator
    ) -> list[TokenDailyResponse]:
        date_to = filters.date_to or self.reporting_date()
        date_from = filters.date_from or (date_to - timedelta(days=29))
        if (date_to - date_from).days > 365:
            raise ManagementValidationError(
                "Daily usage queries may span at most 366 days"
            )
        with self._dao.session(commit=False) as session:
            query = session.query(TokenDailyEntity)
            query = self._scope_query(query, TokenDailyEntity, session, operator)
            if filters.user_id:
                query = query.filter(TokenDailyEntity.user_id == filters.user_id)
            if filters.account_set_id is not None:
                query = query.filter(
                    TokenDailyEntity.account_set_id == filters.account_set_id
                )
            if filters.model:
                query = query.filter(TokenDailyEntity.model == filters.model)
            if filters.role:
                query = query.filter(TokenDailyEntity.role_snapshot == filters.role)
            query = query.filter(
                TokenDailyEntity.stat_date >= date_from.isoformat(),
                TokenDailyEntity.stat_date <= date_to.isoformat(),
            )
            entities = query.order_by(
                TokenDailyEntity.stat_date.desc(), TokenDailyEntity.id.desc()
            ).all()
            return [TokenDailyResponse.model_validate(item) for item in entities]

    def summary(self, stat_date: date, operator: Operator) -> TokenUsageSummaryResponse:
        daily = self.query_daily(
            TokenUsageQueryRequest(date_from=stat_date, date_to=stat_date),
            operator,
        )
        return TokenUsageSummaryResponse(
            stat_date=stat_date.isoformat(),
            input_tokens=sum(item.input_tokens for item in daily),
            output_tokens=sum(item.output_tokens for item in daily),
            total_tokens=sum(item.total_tokens for item in daily),
            call_count=sum(item.call_count for item in daily),
        )

    @staticmethod
    def reporting_date() -> date:
        return datetime.now(timezone.utc).astimezone(SHANGHAI).date()

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ManagementValidationError(
                "page must be at least 1 and page_size must be between 1 and 100"
            )

    @staticmethod
    def _scope_query(query, entity_type, session, operator: Operator):
        if not operator.user_id or not operator.role:
            raise ManagementValidationError("An authenticated user is required")
        if operator.role == "system_admin":
            return query
        if operator.role == "query_user":
            return query.filter(entity_type.user_id == operator.user_id)
        if operator.role != "operations_admin":
            raise ManagementValidationError("The user role cannot read usage")
        account_set_ids = (
            session.query(UserAccountGrantEntity.account_set_id)
            .join(
                AccountSetEntity,
                AccountSetEntity.account_set_id
                == UserAccountGrantEntity.account_set_id,
            )
            .filter(
                UserAccountGrantEntity.user_id == operator.user_id,
                UserAccountGrantEntity.is_active.is_(True),
                AccountSetEntity.is_active.is_(True),
            )
        )
        return query.filter(entity_type.account_set_id.in_(account_set_ids))

    @classmethod
    def _apply_usage_filters(cls, query, filters: TokenUsageQueryRequest):
        if filters.user_id:
            query = query.filter(TokenUsageEntity.user_id == filters.user_id)
        if filters.account_set_id is not None:
            query = query.filter(
                TokenUsageEntity.account_set_id == filters.account_set_id
            )
        if filters.model:
            query = query.filter(TokenUsageEntity.model == filters.model)
        if filters.role:
            query = query.filter(TokenUsageEntity.role_snapshot == filters.role)
        if filters.date_from:
            query = query.filter(
                TokenUsageEntity.gmt_created >= cls._local_day_start(filters.date_from)
            )
        if filters.date_to:
            query = query.filter(
                TokenUsageEntity.gmt_created
                < cls._local_day_start(filters.date_to + timedelta(days=1))
            )
        return query

    @staticmethod
    def _local_day_start(value: date) -> datetime:
        return (
            datetime.combine(value, time.min, SHANGHAI)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

    @staticmethod
    def _as_naive_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


_token_service = TokenService()


def get_token_service() -> TokenService:
    return _token_service
