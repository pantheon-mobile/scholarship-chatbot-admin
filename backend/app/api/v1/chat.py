from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.auth import require_authenticated_session
from app.models.auth import AuthSession
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.chat_service import ChatConfigurationError, ChatGenerationError, ChatService


router = APIRouter(prefix="/chat", tags=["chat"])


def get_service() -> ChatService:
    return ChatService()


@router.post("/messages", response_model=ChatMessageResponse)
async def send_message(
    payload: ChatMessageRequest,
    _current_user: AuthSession = Depends(require_authenticated_session),
    service: ChatService = Depends(get_service),
):
    try:
        return await service.answer(payload.question, payload.bedrock_session_id)
    except ChatConfigurationError:
        raise HTTPException(status_code=503, detail="チャット機能の設定が完了していません。") from None
    except ChatGenerationError:
        raise HTTPException(status_code=502, detail="回答を生成できませんでした。時間をおいて再度お試しください。") from None
