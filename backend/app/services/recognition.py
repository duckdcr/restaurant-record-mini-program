import base64
import json
import time
from datetime import date

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from ..auth import ApiError
from ..models import RecognitionRun, Upload
from ..storage import storage_for
from .menus import latest_menu, normalize_dish


class UpstreamField(BaseModel):
    value: str | float | None = None
    confidence: float = Field(default=0, ge=0, le=1)


class UpstreamRecognition(BaseModel):
    dish_name: UpstreamField
    meal: UpstreamField
    sampled_at: UpstreamField
    keeper: UpstreamField
    amount_g: UpstreamField
    temperature_c: UpstreamField


class RecognitionService:
    def __init__(self, settings, storage):
        self.settings = settings
        self.storage = storage

    async def _call_upstream(self, image_bytes: bytes, mime_type: str, menu_candidates: list[str]) -> dict:
        image_data = base64.b64encode(image_bytes).decode()
        prompt = (
            "读取食品留样标签并只返回JSON。字段为dish_name, meal, sampled_at, keeper, "
            "amount_g, temperature_c；每个字段含value与0到1的confidence。"
            f"菜名候选：{menu_candidates}"
        )
        body = {
            "model": self.settings.ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds) as client:
            response = await client.post(
                self.settings.ai_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.ai_api_key}"},
                json=body,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    def normalize(self, raw: dict, menu_candidates: list[str]) -> dict:
        parsed = UpstreamRecognition.model_validate(raw)
        result = {}
        normalized_candidates = {normalize_dish(name): name for name in menu_candidates}
        for name in ("dish_name", "meal", "sampled_at", "keeper", "amount_g", "temperature_c"):
            field = getattr(parsed, name)
            value = field.value
            source = "ai"
            if name in {"amount_g", "temperature_c"} and value is None:
                value = 125.0 if name == "amount_g" else 4.0
                source = "default"
            elif value is None:
                source = "manual"
            elif name == "dish_name" and normalize_dish(str(value)) in normalized_candidates:
                value = normalized_candidates[normalize_dish(str(value))]
                source = "menu_match"
            result[name] = {
                "value": value,
                "confidence": float(field.confidence),
                "source": source,
                "requires_confirmation": source in {"default", "manual"} or field.confidence < 0.8,
            }
        return result


async def recognize_upload(db: Session, upload: Upload, settings, meal: str, menu_date: date) -> dict:
    run = RecognitionRun(
        upload_id=upload.id,
        model=settings.ai_model,
        model_version=settings.ai_model,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    if not settings.ai_base_url or not settings.ai_api_key or not settings.ai_model:
        run.status = "failed"
        run.error_code = "AI_NOT_CONFIGURED"
        db.commit()
        raise ApiError("AI_NOT_CONFIGURED", "AI识别尚未配置，可切换人工登记", 503)

    menu = latest_menu(db, menu_date, meal)
    candidates = [item.dish_name for item in menu.items] if menu else []
    storage = storage_for(settings)
    service = RecognitionService(settings, storage)
    started = time.perf_counter()
    try:
        raw = await service._call_upstream(storage.read(upload.storage_key), upload.mime_type, candidates)
        structured = service.normalize(raw, candidates)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
        run.status = "failed"
        run.error_code = "AI_INVALID_RESPONSE"
        run.duration_ms = round((time.perf_counter() - started) * 1000)
        db.commit()
        raise ApiError("AI_INVALID_RESPONSE", "AI识别结果不可用，请重试或人工登记", 502, True)
    run.status = "succeeded"
    run.raw_response_json = json.dumps(raw, ensure_ascii=False)
    run.structured_result_json = json.dumps(structured, ensure_ascii=False)
    run.duration_ms = round((time.perf_counter() - started) * 1000)
    db.commit()
    return {"id": run.id, "status": run.status, "fields": structured, "menu_candidates": candidates}

