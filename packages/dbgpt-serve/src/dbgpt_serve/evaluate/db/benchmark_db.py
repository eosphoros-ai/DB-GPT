import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)

from dbgpt.storage.metadata import BaseDao, Model

logger = logging.getLogger(__name__)


class BenchmarkCompareEntity(Model):
    """Single compare record for one input serialNo in one round.

    Fields match the JSON lines produced by FileParseService.write_data_compare_result.
    """

    __tablename__ = "benchmark_compare"
    __table_args__ = (
        UniqueConstraint(
            "round_id", "serial_no", "output_path", name="uk_round_serial_output"
        ),
    )

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="autoincrement id"
    )
    # Round and mode
    round_id = Column(Integer, nullable=False, comment="Benchmark round id")
    mode = Column(String(16), nullable=False, comment="BUILD or EXECUTE")

    # Input & outputs
    serial_no = Column(Integer, nullable=False, comment="Input serial number")
    analysis_model_id = Column(String(255), nullable=False, comment="Analysis model id")
    question = Column(Text, nullable=False, comment="User question")
    self_define_tags = Column(String(255), nullable=True, comment="Self define tags")
    prompt = Column(Text, nullable=True, comment="Prompt text")

    standard_answer_sql = Column(Text, nullable=True, comment="Standard answer SQL")
    llm_output = Column(Text, nullable=True, comment="LLM output text or JSON")
    execute_result = Column(
        Text, nullable=True, comment="Execution result JSON (serialized)"
    )
    error_msg = Column(Text, nullable=True, comment="Error message")

    compare_result = Column(
        String(16), nullable=True, comment="RIGHT/WRONG/FAILED/EXCEPTION"
    )
    is_execute = Column(Boolean, default=False, comment="Whether this is EXECUTE mode")
    llm_count = Column(Integer, default=0, comment="Number of LLM outputs compared")

    # Source path for traceability (original output jsonl file path)
    output_path = Column(
        String(512), nullable=False, comment="Original output file path"
    )

    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )

    Index("idx_bm_comp_round", "round_id")
    Index("idx_bm_comp_mode", "mode")
    Index("idx_bm_comp_serial", "serial_no")


class BenchmarkSummaryEntity(Model):
    """Summary result for one round and one output path.

    Counts of RIGHT/WRONG/FAILED/EXCEPTION, per llm_code.
    """

    __tablename__ = "benchmark_summary"
    __table_args__ = (
        UniqueConstraint(
            "round_id", "output_path", "llm_code", name="uk_round_output_llm"
        ),
    )

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="autoincrement id"
    )
    round_id = Column(Integer, nullable=False, comment="Benchmark round id")
    output_path = Column(
        String(512), nullable=False, comment="Original output file path"
    )
    evaluate_code = Column(
        String(255),
        nullable=True,
        comment="Task evaluate_code (unique id per submitted task)",
    )
    llm_code = Column(String(255), nullable=True, comment="LLM code for this summary")

    right = Column(Integer, default=0, comment="RIGHT count")
    wrong = Column(Integer, default=0, comment="WRONG count")
    failed = Column(Integer, default=0, comment="FAILED count")
    exception = Column(Integer, default=0, comment="EXCEPTION count")

    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )

    Index("idx_bm_sum_round", "round_id")
    Index("idx_bm_sum_task", "task_serial_no")


class BenchmarkResultDao(BaseDao):
    """DAO for benchmark summary results."""

    def upsert_summary(
        self,
        round_id: int,
        output_path: str,
        llm_code: Optional[str],
        right: int,
        wrong: int,
        failed: int,
        exception: int,
        evaluate_code: Optional[str] = None,
    ):
        """Upsert summary counts directly into DB (per llm_code) with task"""
        with self.session() as session:
            existing = (
                session.query(BenchmarkSummaryEntity)
                .filter(
                    BenchmarkSummaryEntity.round_id == round_id,
                    BenchmarkSummaryEntity.output_path == output_path,
                    BenchmarkSummaryEntity.llm_code == llm_code,
                )
                .first()
            )
            if existing:
                existing.right = right
                existing.wrong = wrong
                existing.failed = failed
                existing.exception = exception
                if evaluate_code is not None:
                    existing.evaluate_code = evaluate_code
                existing.gmt_modified = datetime.now()
                session.commit()
                return existing.id
            else:
                summary = BenchmarkSummaryEntity(
                    round_id=round_id,
                    output_path=output_path,
                    evaluate_code=evaluate_code,
                    llm_code=llm_code,
                    right=right,
                    wrong=wrong,
                    failed=failed,
                    exception=exception,
                )
                session.add(summary)
                session.commit()

    # Basic query helpers
    def list_compare_by_round(self, round_id: int, limit: int = 100, offset: int = 0):
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkCompareEntity)
                .filter(BenchmarkCompareEntity.round_id == round_id)
                .order_by(desc(BenchmarkCompareEntity.id))
                .limit(limit)
                .offset(offset)
                .all()
            )

    def get_summary(
        self, round_id: int, output_path: str
    ) -> Optional[BenchmarkSummaryEntity]:
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkSummaryEntity)
                .filter(
                    BenchmarkSummaryEntity.round_id == round_id,
                    BenchmarkSummaryEntity.output_path == output_path,
                )
                .first()
            )

    def list_summaries_by_round(self, round_id: int, limit: int = 100, offset: int = 0):
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkSummaryEntity)
                .filter(BenchmarkSummaryEntity.round_id == round_id)
                .order_by(desc(BenchmarkSummaryEntity.id))
                .limit(limit)
                .offset(offset)
                .all()
            )

    def list_rounds(self, limit: int = 100, offset: int = 0):
        with self.session(commit=False) as session:
            rows = (
                session.query(
                    BenchmarkSummaryEntity.round_id,
                    func.max(BenchmarkSummaryEntity.gmt_created).label("last_time"),
                )
                .group_by(BenchmarkSummaryEntity.round_id)
                .order_by(desc("last_time"))
                .limit(limit)
                .offset(offset)
                .all()
            )
            # return only round ids in order
            return [r[0] for r in rows]

    def list_summaries(self, limit: int = 100, offset: int = 0):
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkSummaryEntity)
                .order_by(desc(BenchmarkSummaryEntity.id))
                .limit(limit)
                .offset(offset)
                .all()
            )

    def get_summary_by_id(self, summary_id: int) -> Optional[BenchmarkSummaryEntity]:
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkSummaryEntity)
                .filter(BenchmarkSummaryEntity.id == summary_id)
                .first()
            )

    def list_tasks(self, limit: int = 100, offset: int = 0) -> List[str]:
        """List submitted task ids (evaluate_code), ordered by latest summary time."""
        with self.session(commit=False) as session:
            rows = (
                session.query(
                    BenchmarkSummaryEntity.evaluate_code,
                    func.max(BenchmarkSummaryEntity.gmt_created).label("last_time"),
                )
                .filter(BenchmarkSummaryEntity.evaluate_code.isnot(None))
                .group_by(BenchmarkSummaryEntity.evaluate_code)
                .order_by(desc("last_time"))
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [r[0] for r in rows]

    def list_summaries_by_task(
        self, evaluate_code: str, limit: int = 1000, offset: int = 0
    ):
        """List summaries for a given task (may include multiple rounds)."""
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkSummaryEntity)
                .filter(BenchmarkSummaryEntity.evaluate_code == evaluate_code)
                .order_by(desc(BenchmarkSummaryEntity.id))
                .limit(limit)
                .offset(offset)
                .all()
            )
