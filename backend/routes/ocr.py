from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from backend.config import settings
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.schemas import AskResponse
from backend.services.auth_service import load_auth_context
from backend.services.conversation_service import ConversationNotFoundError
from backend.services.ocr_service import ask_with_image
from backend.services.ticket_service import TicketError

router = APIRouter(tags=["ocr"])


def _parse_optional_uuid(raw: str | None) -> UUID | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return UUID(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="conversation_id 不是合法 UUID") from exc


@router.post("/ocr", response_model=AskResponse)
async def ocr_ask(
    request: Request,
    image: UploadFile = File(...),
    question: str | None = Form(default=None),
    conversation_id: str | None = Form(default=None),
) -> AskResponse:
    """上传截图识文后进入既有问答；全员可用。ocr_failed 时 hit 为 null，不建工单。"""
    try:
        context = load_auth_context(request)
        if context is None:
            raise HTTPException(status_code=401, detail="未登录")

        raw = await image.read()
        if not raw:
            raise HTTPException(status_code=400, detail="图片内容为空")
        if len(raw) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="图片过大")

        result = ask_with_image(
            image_bytes=raw,
            content_type=image.content_type,
            filename=image.filename,
            user_prompt=(question or "").strip() or None,
            allowed_spaces=context.allowed_spaces,
            user_id=context.user.id,
            user_role=context.user.role,
            advisor_id=context.user.advisor_id,
            conversation_id=_parse_optional_uuid(conversation_id),
            position_key=context.user.position_key,
        )
    except HTTPException:
        raise
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="图片问答处理失败") from exc

    return AskResponse(
        answer=result.answer,
        hit=result.hit,
        sources=result.sources,
        conversation_id=result.conversation_id,
        ticket_id=result.ticket_id,
        owner=result.owner,
        error_type=result.error_type,
        llm_called=result.llm_called,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        extracted_text=result.extracted_text,
        extract_method=result.extract_method,
    )
