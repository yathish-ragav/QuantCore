from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_market_index_service
from quantcore.schemas.indexes import (
    IndexConstituentResponse,
    IndexListResponse,
    MarketIndexResponse,
    ResearchUniverseResponse,
)
from quantcore.services.market_index_service import MarketIndexService


router = APIRouter(
    prefix="/indexes",
    tags=["Indexes"],
)


@router.get("", response_model=IndexListResponse)
def list_indexes(
    service: MarketIndexService = Depends(get_market_index_service),
):
    return IndexListResponse(
        indexes=[
            MarketIndexResponse(
                id=index.id,
                key=index.key,
                name=index.name,
                provider=index.provider,
                methodology_reference=index.methodology_reference,
                source_reference=index.source_reference,
                is_active=index.is_active,
            )
            for index in service.list_active()
        ]
    )


@router.get("/{key}", response_model=MarketIndexResponse)
def get_index(
    key: str,
    service: MarketIndexService = Depends(get_market_index_service),
):
    index = service.get(key)
    return MarketIndexResponse(
        id=index.id,
        key=index.key,
        name=index.name,
        provider=index.provider,
        methodology_reference=index.methodology_reference,
        source_reference=index.source_reference,
        is_active=index.is_active,
    )


@router.get("/{key}/constituents", response_model=list[IndexConstituentResponse])
def get_index_constituents(
    key: str,
    as_of: datetime = Query(...),
    service: MarketIndexService = Depends(get_market_index_service),
):
    members = service.constituents_as_of(key, as_of=as_of)
    return [
        IndexConstituentResponse(
            security_id=member.security_id,
            symbol=member.security.symbol,
            exchange=member.security.exchange,
            company_id=member.security.company_id,
            effective_from=member.effective_from,
            effective_to=member.effective_to,
            weight=member.weight,
            source_reference=member.source_reference,
            known_at=member.known_at,
            observed_at=member.observed_at,
        )
        for member in members
    ]


@router.get("/{key}/universe", response_model=ResearchUniverseResponse)
def resolve_index_universe(
    key: str,
    as_of: datetime = Query(...),
    service: MarketIndexService = Depends(get_market_index_service),
):
    snapshot = service.resolve(key, as_of=as_of)
    return ResearchUniverseResponse(
        index_key=snapshot.index_key,
        as_of=snapshot.as_of,
        security_ids=list(snapshot.security_ids),
        fingerprint=snapshot.fingerprint,
        size=snapshot.size,
    )
