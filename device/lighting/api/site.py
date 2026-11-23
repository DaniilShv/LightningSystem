from fastapi import APIRouter

from lighting.api.deps import Service
from lighting.api.dto import SiteOut, SiteUpdate

router = APIRouter(prefix="/site", tags=["Объект"])


@router.get("", summary="Объект: имя и тариф")
def get_site(service: Service) -> SiteOut:
    site = service.get_site()
    return SiteOut(name=site.name, tariff_rub_per_kwh=site.tariff_rub_per_kwh)


@router.patch("", summary="Изменить имя объекта или тариф ₽/кВт·ч")
def update_site(body: SiteUpdate, service: Service) -> SiteOut:
    site = service.update_site(body.name, body.tariff_rub_per_kwh)
    return SiteOut(name=site.name, tariff_rub_per_kwh=site.tariff_rub_per_kwh)
