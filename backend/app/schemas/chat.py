from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    bedrock_session_id: str | None = Field(default=None, max_length=2048)


class ChatCitation(BaseModel):
    title: str
    uri: str | None = None
    excerpt: str | None = None


class ChatMessageResponse(BaseModel):
    answer: str
    answer_type: str
    bedrock_session_id: str | None = None
    citations: list[ChatCitation]
