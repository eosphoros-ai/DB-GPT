import json
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

    id = Column(Integer, primary_key=True, autoincrement=True, comment="autoincrement id")
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
    execute_result = Column(Text, nullable=True, comment="Execution result JSON (serialized)")
    error_msg = Column(Text, nullable=True, comment="Error message")

    compare_result = Column(String(16), nullable=True, comment="RIGHT/WRONG/FAILED/EXCEPTION")
    is_execute = Column(Boolean, default=False, comment="Whether this is EXECUTE mode")
    llm_count = Column(Integer, default=0, comment="Number of LLM outputs compared")

    # Source path for traceability (original output jsonl file path)
    output_path = Column(String(512), nullable=False, comment="Original output file path")

    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="Record update time")

    Index("idx_bm_comp_round", "round_id")
    Index("idx_bm_comp_mode", "mode")
    Index("idx_bm_comp_serial", "serial_no")


class BenchmarkSummaryEntity(Model):
    """Summary result for one round and one output path.

    Counts of RIGHT/WRONG/FAILED/EXCEPTION.
    """

    __tablename__ = "benchmark_summary"
    __table_args__ = (
        UniqueConstraint("round_id", "output_path", name="uk_round_output"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="autoincrement id")
    round_id = Column(Integer, nullable=False, comment="Benchmark round id")
    output_path = Column(String(512), nullable=False, comment="Original output file path")

    right = Column(Integer, default=0, comment="RIGHT count")
    wrong = Column(Integer, default=0, comment="WRONG count")
    failed = Column(Integer, default=0, comment="FAILED count")
    exception = Column(Integer, default=0, comment="EXCEPTION count")

    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="Record update time")

    Index("idx_bm_sum_round", "round_id")


class BenchmarkResultDao(BaseDao):
    """DAO for benchmark compare and summary results."""

    def write_compare_results(
        self,
        round_id: int,
        mode: str,  # "BUILD" or "EXECUTE"
        output_path: str,
        records: List[dict],
        is_execute: bool,
        llm_count: int,
    ) -> int:
        """Write multiple compare records to DB.

        records: each dict contains keys like in FileParseService.write_data_compare_result rows.
        Returns number of records inserted.
        """
        inserted = 0
        with self.session() as session:
            for r in records:
                try:
                    entity = BenchmarkCompareEntity(
                        round_id=round_id,
                        mode=mode,
                        serial_no=r.get("serialNo"),
                        analysis_model_id=r.get("analysisModelId"),
                        question=r.get("question"),
                        self_define_tags=r.get("selfDefineTags"),
                        prompt=r.get("prompt"),
                        standard_answer_sql=r.get("standardAnswerSql"),
                        llm_output=r.get("llmOutput"),
                        execute_result=json.dumps(r.get("executeResult")) if r.get("executeResult") is not None else None,
                        error_msg=r.get("errorMsg"),
                        compare_result=r.get("compareResult"),
                        is_execute=is_execute,
                        llm_count=llm_count,
                        output_path=output_path,
                    )
                    session.add(entity)
                    inserted += 1
                except Exception as e:
                    logger.error(f"Insert compare record failed: {e}")
            session.commit()
        return inserted

    def compute_and_save_summary(self, round_id: int, output_path: str) -> Optional[int]:
        """Compute summary from compare table and save to summary table.
        Returns summary id if saved, else None.
        """
        with self.session() as session:
            # compute counts
            q = (
                session.query(BenchmarkCompareEntity.compare_result)
                .filter(
                    BenchmarkCompareEntity.round_id == round_id,
                    BenchmarkCompareEntity.output_path == output_path,
                )
                .all()
            )
            right = sum(1 for x in q if x[0] == "RIGHT")
            wrong = sum(1 for x in q if x[0] == "WRONG")
            failed = sum(1 for x in q if x[0] == "FAILED")
            exception = sum(1 for x in q if x[0] == "EXCEPTION")

            # upsert summary
            existing = (
                session.query(BenchmarkSummaryEntity)
                .filter(
                    BenchmarkSummaryEntity.round_id == round_id,
                    BenchmarkSummaryEntity.output_path == output_path,
                )
                .first()
            )
            if existing:
                existing.right = right
                existing.wrong = wrong
                existing.failed = failed
                existing.exception = exception
                existing.gmt_modified = datetime.now()
                session.commit()
                return existing.id
            else:
                summary = BenchmarkSummaryEntity(
                    round_id=round_id,
                    output_path=output_path,
                    right=right,
                    wrong=wrong,
                    failed=failed,
                    exception=exception,
                )
                session.add(summary)
                session.commit()
                return summary.id

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

    def get_summary(self, round_id: int, output_path: str) -> Optional[BenchmarkSummaryEntity]:
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkSummaryEntity)
                .filter(
                    BenchmarkSummaryEntity.round_id == round_id,
                    BenchmarkSummaryEntity.output_path == output_path,
                )
                .first()
            )

    # New helpers for listing summaries and detail by id
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

    def list_compare_by_round_and_path(
        self, round_id: int, output_path: str, limit: int = 200, offset: int = 0
    ):
        with self.session(commit=False) as session:
            return (
                session.query(BenchmarkCompareEntity)
                .filter(
                    BenchmarkCompareEntity.round_id == round_id,
                    BenchmarkCompareEntity.output_path == output_path,
                )
                .order_by(desc(BenchmarkCompareEntity.id))
                .limit(limit)
                .offset(offset)
                .all()
            )

