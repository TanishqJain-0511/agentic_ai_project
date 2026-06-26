import json
import os
import asyncio
import httpx
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.mutual_fund import MutualFund

MFAPI_BASE = "https://api.mfapi.in/mf"
_METADATA_PATH = os.path.join(os.path.dirname(__file__), "../data/mutual_fund_metadata.json")
_MAX_CONCURRENT = 10


def _load_curated_metadata() -> dict:
    with open(_METADATA_PATH, "r") as f:
        entries = json.load(f)
    return {e["scheme_code"]: e for e in entries}


async def _fetch_fund(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    scheme_code: str,
    meta: dict,
) -> Optional[dict]:
    async with semaphore:
        try:
            resp = await client.get(f"{MFAPI_BASE}/{scheme_code}", timeout=10)
            resp.raise_for_status()
            data = resp.json()

            scheme_name = data.get("meta", {}).get("scheme_name", "Unknown")
            latest_nav_dict = data.get("data", [{}])[0]
            net_asset_value = (
                float(latest_nav_dict["nav"]) if latest_nav_dict.get("nav") else None
            )
            nav_date = latest_nav_dict.get("date")

            return {
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "net_asset_value": net_asset_value,
                "nav_date": nav_date,
                "category": meta.get("category"),
                "risk_grade": meta.get("risk_grade"),
                "expense_ratio": meta.get("expense_ratio"),
                "aum_in_crores": meta.get("aum_in_crores"),
            }
        except Exception:
            return None


async def _fetch_all_funds(metadata: dict) -> Tuple[List[dict], int]:
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[
                _fetch_fund(client, semaphore, scheme_code, meta)
                for scheme_code, meta in metadata.items()
            ]
        )
    fetched = [r for r in results if r is not None]
    failed = sum(1 for r in results if r is None)
    return fetched, failed


async def sync_mutual_funds(db: AsyncSession) -> dict:
    metadata = _load_curated_metadata()
    fetched, failed = await _fetch_all_funds(metadata)

    scheme_codes = [d["scheme_code"] for d in fetched]
    existing_result = await db.execute(
        select(MutualFund).where(MutualFund.scheme_code.in_(scheme_codes))
    )
    existing = {f.scheme_code: f for f in existing_result.scalars().all()}

    for fund_data in fetched:
        fund = existing.get(fund_data["scheme_code"])
        if fund:
            for key, value in fund_data.items():
                setattr(fund, key, value)
        else:
            db.add(MutualFund(**fund_data))

    await db.commit()

    synced = len(fetched)
    return {
        "synced": synced,
        "failed": failed,
        "message": f"Sync complete. {synced} funds updated, {failed} failed.",
    }


async def get_all_mutual_funds(
    db: AsyncSession,
    category: Optional[str] = None,
    risk_grade: Optional[str] = None,
):
    query = select(MutualFund)
    if category:
        query = query.where(MutualFund.category == category)
    if risk_grade:
        query = query.where(MutualFund.risk_grade == risk_grade)
    result = await db.execute(query)
    return result.scalars().all()


async def get_mutual_fund_by_scheme_code(db: AsyncSession, scheme_code: str):
    result = await db.execute(
        select(MutualFund).where(MutualFund.scheme_code == scheme_code)
    )
    return result.scalar_one_or_none()
