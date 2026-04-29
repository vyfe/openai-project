from datetime import datetime
from typing import Optional

from models import RoundCell


class RoundCellRepo:
    @staticmethod
    def create(round_id: int, child_id: int, cell_status: str = 'idle', assistant_output: Optional[str] = None, error_json: Optional[str] = None, latency_ms: Optional[int] = None, request_id: Optional[str] = None) -> RoundCell:
        return RoundCell.create(
            round=round_id,
            child=child_id,
            cell_status=cell_status,
            assistant_output=assistant_output,
            error_json=error_json,
            latency_ms=latency_ms,
            request_id=request_id,
            updated_at=datetime.now(),
        )

    @staticmethod
    def list_by_round(round_id: int) -> list[RoundCell]:
        return list(RoundCell.select().where(RoundCell.round == round_id))

    @staticmethod
    def get(round_id: int, child_id: int) -> Optional[RoundCell]:
        return (
            RoundCell.select()
            .where((RoundCell.round == round_id) & (RoundCell.child == child_id))
            .first()
        )

    @staticmethod
    def upsert(round_id: int, child_id: int, **kwargs) -> RoundCell:
        cell = RoundCellRepo.get(round_id, child_id)
        if cell:
            kwargs['updated_at'] = datetime.now()
            RoundCell.update(**kwargs).where(RoundCell.id == cell.id).execute()
            return RoundCell.get_by_id(cell.id)
        return RoundCellRepo.create(round_id, child_id, **kwargs)
