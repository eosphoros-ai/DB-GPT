"""Repository layer for persisting provenance, metrics, and reports."""

from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, FinancialMetric, Provenance, Report


class Store:
    """A thin wrapper around a SQLite database for finance research data."""

    def __init__(self, db_path: str = "finance_research.db"):
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def session(self) -> Session:
        return self._session_factory()

    def add_provenance(self, provenance: Provenance) -> Provenance:
        with self.session() as session:
            session.add(provenance)
            session.commit()
            session.refresh(provenance)
            return provenance

    def add_metrics(self, metrics: List[FinancialMetric]) -> None:
        with self.session() as session:
            session.add_all(metrics)
            session.commit()

    def list_metrics(
        self,
        company_name: Optional[str] = None,
        metric_name: Optional[str] = None,
    ) -> List[FinancialMetric]:
        with self.session() as session:
            query = session.query(FinancialMetric)
            if company_name:
                query = query.filter(FinancialMetric.company_name == company_name)
            if metric_name:
                query = query.filter(FinancialMetric.metric_name == metric_name)
            return query.all()

    def add_report(self, report: Report) -> Report:
        with self.session() as session:
            session.add(report)
            session.commit()
            session.refresh(report)
            return report
