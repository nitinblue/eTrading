"""
Data Explorer API Router — Structured query builder for all 19 DB tables.

NO raw SQL — uses table/column whitelist with typed filter execution via SQLAlchemy ORM.
Mounted in approval_api.py at /api/explorer prefix.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import inspect, func
from sqlalchemy.types import (
    String as SAString,
    Text as SAText,
    Integer as SAInteger,
    Numeric as SANumeric,
    Float as SAFloat,
    Boolean as SABoolean,
    DateTime as SADateTime,
    Date as SADate,
    JSON as SAJSON,
    Enum as SAEnum,
)

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import (
    SymbolORM,
    PortfolioORM,
    PositionORM,
    PositionGreeksSnapshotORM,
    PositionPnLSnapshotORM,
    TradeORM,
    LegORM,
    StrategyORM,
    OrderORM,
    TradeEventORM,
    RecognizedPatternORM,
    DailyPerformanceORM,
    GreeksHistoryORM,
    WhatIfPortfolioConfigORM,
    MarketDataSnapshotORM,
    RecommendationORM,
    WatchlistORM,
    WorkflowStateORM,
    DecisionLogORM,
)

logger = logging.getLogger(__name__)

MAX_ROWS = 1000


# ---------------------------------------------------------------------------
# Table registry — built from ORM classes at module load
# ---------------------------------------------------------------------------

def _sa_type_to_logical(sa_type) -> str:
    """Map SQLAlchemy column type to a logical type string."""
    if isinstance(sa_type, (SABoolean,)):
        return 'boolean'
    if isinstance(sa_type, (SAInteger,)):
        return 'numeric'
    if isinstance(sa_type, (SANumeric, SAFloat)):
        return 'numeric'
    if isinstance(sa_type, (SADateTime, SADate)):
        return 'datetime'
    if isinstance(sa_type, (SAJSON,)):
        return 'json'
    # String, Text, Enum, and everything else
    return 'string'


class ColumnMeta:
    __slots__ = ('name', 'logical_type', 'nullable')

    def __init__(self, name: str, logical_type: str, nullable: bool):
        self.name = name
        self.logical_type = logical_type
        self.nullable = nullable

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'type': self.logical_type,
            'nullable': self.nullable,
        }


class TableMeta:
    __slots__ = ('table_name', 'orm_class', 'columns')

    def __init__(self, table_name: str, orm_class, columns: List[ColumnMeta]):
        self.table_name = table_name
        self.orm_class = orm_class
        self.columns = columns

    def column_map(self) -> Dict[str, ColumnMeta]:
        return {c.name: c for c in self.columns}


_ORM_CLASSES = [
    SymbolORM,
    PortfolioORM,
    PositionORM,
    PositionGreeksSnapshotORM,
    PositionPnLSnapshotORM,
    TradeORM,
    LegORM,
    StrategyORM,
    OrderORM,
    TradeEventORM,
    RecognizedPatternORM,
    DailyPerformanceORM,
    GreeksHistoryORM,
    WhatIfPortfolioConfigORM,
    MarketDataSnapshotORM,
    RecommendationORM,
    WatchlistORM,
    WorkflowStateORM,
    DecisionLogORM,
]


def _build_registry() -> Dict[str, TableMeta]:
    registry: Dict[str, TableMeta] = {}
    for orm_cls in _ORM_CLASSES:
        table_name = orm_cls.__tablename__
        mapper = inspect(orm_cls)
        cols = []
        for attr in mapper.column_attrs:
            col = attr.columns[0]
            cols.append(ColumnMeta(
                name=attr.key,
                logical_type=_sa_type_to_logical(col.type),
                nullable=col.nullable if col.nullable is not None else True,
            ))
        registry[table_name] = TableMeta(table_name, orm_cls, cols)
    return registry


TABLE_REGISTRY = _build_registry()

# Valid operators per logical type
OPERATORS_BY_TYPE = {
    'string':   ['eq', 'neq', 'contains', 'starts_with', 'in'],
    'numeric':  ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between'],
    'datetime': ['eq', 'gt', 'gte', 'lt', 'lte', 'between'],
    'boolean':  ['eq'],
    'json':     ['contains'],
}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class FilterSpec(BaseModel):
    column: str
    operator: str  # eq, neq, gt, gte, lt, lte, contains, starts_with, in, between
    value: str
    value2: Optional[str] = None  # for 'between'


class ExplorerQuery(BaseModel):
    table: str
    columns: Optional[List[str]] = None  # None = all columns
    filters: Optional[List[FilterSpec]] = None
    sort_by: Optional[str] = None
    sort_desc: bool = False
    limit: int = 100
    offset: int = 0


# ---------------------------------------------------------------------------
# Filter application
# ---------------------------------------------------------------------------

def _parse_value(raw: str, logical_type: str) -> Any:
    """Parse a string value to the correct Python type for filtering."""
    if logical_type == 'numeric':
        try:
            if '.' in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw
    if logical_type == 'datetime':
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return raw
    if logical_type == 'boolean':
        return raw.lower() in ('true', '1', 'yes')
    return raw


def _apply_filter(query, orm_cls, fspec: FilterSpec, col_meta: ColumnMeta):
    """Apply a single filter to a SQLAlchemy query."""
    col_attr = getattr(orm_cls, fspec.column)
    val = _parse_value(fspec.value, col_meta.logical_type)

    op = fspec.operator
    if op == 'eq':
        return query.filter(col_attr == val)
    elif op == 'neq':
        return query.filter(col_attr != val)
    elif op == 'gt':
        return query.filter(col_attr > val)
    elif op == 'gte':
        return query.filter(col_attr >= val)
    elif op == 'lt':
        return query.filter(col_attr < val)
    elif op == 'lte':
        return query.filter(col_attr <= val)
    elif op == 'contains':
        return query.filter(col_attr.ilike(f'%{val}%'))
    elif op == 'starts_with':
        return query.filter(col_attr.ilike(f'{val}%'))
    elif op == 'in':
        values = [v.strip() for v in fspec.value.split(',')]
        return query.filter(col_attr.in_(values))
    elif op == 'between':
        val2 = _parse_value(fspec.value2 or fspec.value, col_meta.logical_type)
        return query.filter(col_attr.between(val, val2))
    else:
        raise HTTPException(400, f"Unknown operator '{op}'")


def _serialize_value(val: Any) -> Any:
    """Convert ORM values to JSON-safe types."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='replace')
    return val


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def create_explorer_router() -> APIRouter:
    """Create the data explorer API router."""

    router = APIRouter()

    @router.get("/tables")
    async def list_tables():
        """List all tables with column metadata and row counts."""
        result = []
        with session_scope() as session:
            for name, meta in sorted(TABLE_REGISTRY.items()):
                try:
                    count = session.query(func.count()).select_from(meta.orm_class).scalar() or 0
                except Exception:
                    count = 0
                result.append({
                    'name': name,
                    'row_count': count,
                    'columns': [c.to_dict() for c in meta.columns],
                })
        return result

    @router.get("/tables/{table_name}")
    async def table_detail(table_name: str):
        """Single table metadata + 5 sample rows."""
        meta = TABLE_REGISTRY.get(table_name)
        if not meta:
            raise HTTPException(404, f"Table '{table_name}' not found")

        with session_scope() as session:
            count = session.query(func.count()).select_from(meta.orm_class).scalar() or 0
            samples = session.query(meta.orm_class).limit(5).all()

            col_names = [c.name for c in meta.columns]
            sample_rows = []
            for row in samples:
                sample_rows.append({
                    cn: _serialize_value(getattr(row, cn, None))
                    for cn in col_names
                })

        return {
            'name': table_name,
            'row_count': count,
            'columns': [c.to_dict() for c in meta.columns],
            'sample_rows': sample_rows,
        }

    @router.post("/query")
    async def execute_query(body: ExplorerQuery):
        """Execute a structured query. No raw SQL."""
        meta = TABLE_REGISTRY.get(body.table)
        if not meta:
            raise HTTPException(404, f"Table '{body.table}' not found")

        col_map = meta.column_map()
        orm_cls = meta.orm_class

        # Validate requested columns
        if body.columns:
            for cn in body.columns:
                if cn not in col_map:
                    raise HTTPException(400, f"Column '{cn}' not found in table '{body.table}'")
            select_cols = body.columns
        else:
            select_cols = [c.name for c in meta.columns]

        # Clamp limit
        limit = min(body.limit, MAX_ROWS)

        with session_scope() as session:
            q = session.query(orm_cls)

            # Apply filters
            if body.filters:
                for fspec in body.filters:
                    if fspec.column not in col_map:
                        raise HTTPException(400, f"Column '{fspec.column}' not found in table '{body.table}'")
                    cmeta = col_map[fspec.column]
                    valid_ops = OPERATORS_BY_TYPE.get(cmeta.logical_type, [])
                    if fspec.operator not in valid_ops:
                        raise HTTPException(
                            400,
                            f"Operator '{fspec.operator}' not valid for column '{fspec.column}' (type: {cmeta.logical_type}). Valid: {valid_ops}",
                        )
                    q = _apply_filter(q, orm_cls, fspec, cmeta)

            # Sort
            if body.sort_by:
                if body.sort_by not in col_map:
                    raise HTTPException(400, f"Sort column '{body.sort_by}' not found")
                sort_attr = getattr(orm_cls, body.sort_by)
                q = q.order_by(sort_attr.desc() if body.sort_desc else sort_attr.asc())

            total = q.count()
            rows = q.offset(body.offset).limit(limit).all()

            data = []
            for row in rows:
                data.append({
                    cn: _serialize_value(getattr(row, cn, None))
                    for cn in select_cols
                })

        return {
            'table': body.table,
            'total': total,
            'offset': body.offset,
            'limit': limit,
            'columns': [col_map[cn].to_dict() for cn in select_cols],
            'rows': data,
        }

    @router.post("/query/csv")
    async def export_csv(body: ExplorerQuery):
        """Execute query and return results as CSV download."""
        meta = TABLE_REGISTRY.get(body.table)
        if not meta:
            raise HTTPException(404, f"Table '{body.table}' not found")

        col_map = meta.column_map()
        orm_cls = meta.orm_class

        if body.columns:
            for cn in body.columns:
                if cn not in col_map:
                    raise HTTPException(400, f"Column '{cn}' not found")
            select_cols = body.columns
        else:
            select_cols = [c.name for c in meta.columns]

        limit = min(body.limit, MAX_ROWS)

        with session_scope() as session:
            q = session.query(orm_cls)

            if body.filters:
                for fspec in body.filters:
                    if fspec.column not in col_map:
                        raise HTTPException(400, f"Column '{fspec.column}' not found")
                    cmeta = col_map[fspec.column]
                    q = _apply_filter(q, orm_cls, fspec, cmeta)

            if body.sort_by and body.sort_by in col_map:
                sort_attr = getattr(orm_cls, body.sort_by)
                q = q.order_by(sort_attr.desc() if body.sort_desc else sort_attr.asc())

            rows = q.offset(body.offset).limit(limit).all()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(select_cols)
            for row in rows:
                writer.writerow([
                    _serialize_value(getattr(row, cn, None))
                    for cn in select_cols
                ])

        output.seek(0)
        filename = f"{body.table}_export.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
