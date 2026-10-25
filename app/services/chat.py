from sqlalchemy.orm import Session

from app.models import Conversation, Message
from app.services import faq, llm

SYSTEM_PROMPT = (
    "你是「听书App」的智能客服。用简洁、准确的中文回答用户问题。"
    "回答范围限于订阅、会员、播放、下载、账号、售后等听书相关问题。"
    "优先依据下方参考知识库回答,不要编造。知识库无法覆盖时,引导用户联系人工客服。"
)


def handle_message(db: Session, message: str, conversation_id: int | None) -> tuple[str, int]:
    if conversation_id is None:
        conv = Conversation()
        db.add(conv)
        db.flush()
        conversation_id = conv.id
    elif db.get(Conversation, conversation_id) is None:
        conv = Conversation(id=conversation_id)
        db.add(conv)
        db.flush()

    db.add(Message(conversation_id=conversation_id, role="user", content=message))

    context = faq.search(db, message)
    system = SYSTEM_PROMPT
    if context:
        lines = "\n".join(f"Q: {f.question}\nA: {f.answer}" for f in context)
        system += f"\n\n参考知识库:\n{lines}"

    reply = llm.generate(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ]
    )

    db.add(Message(conversation_id=conversation_id, role="assistant", content=reply))
    db.commit()
    return reply, conversation_id
