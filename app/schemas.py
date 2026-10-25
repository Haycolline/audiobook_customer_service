from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int


class FAQItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    category: str


class FAQCreate(BaseModel):
    question: str
    answer: str
    category: str = ""
