from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Path
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, and_
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.message import Message, MessageAttachment, message_reactions
from app.schemas.message import MessageCreate, MessageOut, MessageListItem, ReactionCreate, AttachmentOut
from app.services.file_storage import save_message_attachment, get_attachment_path, delete_attachment
from app.core.utils.emoji import is_valid_emoji, count_reactions

router = APIRouter()

# ─────────────────────────────────────────────
# 📤 Send a new message
# ─────────────────────────────────────────────
@router.post("/", response_model=MessageOut, status_code=201)
async def send_message(
    message: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify recipient exists
    recipient_result = await db.execute(select(User).where(User.id == message.recipient_id))
    recipient = recipient_result.scalar_one_or_none()
    
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    # Create message
    new_message = Message(
        sender_id=current_user.id,
        recipient_id=message.recipient_id,
        content=message.content
    )
    
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    # Load relationships for the response
    new_message.sender = current_user
    new_message.recipient = recipient
    
    return new_message

# ─────────────────────────────────────────────
# 📎 Upload file attachment to a message
# ─────────────────────────────────────────────
@router.post("/{message_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    message_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify message exists and user is the sender
    message_result = await db.execute(
        select(Message).where(
            and_(
                Message.id == message_id,
                Message.sender_id == current_user.id
            )
        )
    )
    message = message_result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission")
    
    # Save file
    file_info = await save_message_attachment(file, current_user.id)
    
    # Create attachment record
    attachment = MessageAttachment(
        message_id=message_id,
        **file_info
    )
    
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    
    return attachment

# ─────────────────────────────────────────────
# 📂 Download an attachment
# ─────────────────────────────────────────────
@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get attachment info
    attachment_result = await db.execute(
        select(MessageAttachment, Message).join(
            Message, MessageAttachment.message_id == Message.id
        ).where(
            and_(
                MessageAttachment.id == attachment_id,
                (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
            )
        )
    )
    result = attachment_result.first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Attachment not found or you don't have permission")
    
    attachment = result[0]
    
    # Get file path and return file
    file_path = get_attachment_path(attachment.file_path)
    return FileResponse(
        path=file_path,
        filename=attachment.file_name,
        media_type=attachment.mime_type
    )

# ─────────────────────────────────────────────
# 👍 Add reaction to a message
# ─────────────────────────────────────────────
@router.post("/{message_id}/reactions", status_code=201)
async def add_reaction(
    message_id: int,
    reaction: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify message exists and user is either sender or recipient
    message_result = await db.execute(
        select(Message).where(
            and_(
                Message.id == message_id,
                (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
            )
        )
    )
    message = message_result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission")
    
    # Validate emoji
    if not is_valid_emoji(reaction.emoji):
        raise HTTPException(status_code=400, detail="Invalid emoji format")
    
    # Check if reaction already exists
    stmt = select(message_reactions).where(
        and_(
            message_reactions.c.message_id == message_id,
            message_reactions.c.user_id == current_user.id
        )
    )
    existing = await db.execute(stmt)
    
    if existing.first():
        # Update existing reaction
        await db.execute(
            message_reactions.update().where(
                and_(
                    message_reactions.c.message_id == message_id,
                    message_reactions.c.user_id == current_user.id
                )
            ).values(emoji=reaction.emoji)
        )
    else:
        # Insert new reaction
        await db.execute(
            message_reactions.insert().values(
                message_id=message_id,
                user_id=current_user.id,
                emoji=reaction.emoji
            )
        )
    
    await db.commit()
    return {"status": "success"}

# ─────────────────────────────────────────────
# ❌ Remove reaction from a message
# ─────────────────────────────────────────────
@router.delete("/{message_id}/reactions", status_code=204)
async def remove_reaction(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Delete the reaction
    await db.execute(
        message_reactions.delete().where(
            and_(
                message_reactions.c.message_id == message_id,
                message_reactions.c.user_id == current_user.id
            )
        )
    )
    
    await db.commit()
    return None

# ─────────────────────────────────────────────
# 📥 List received messages
# ─────────────────────────────────────────────
@router.get("/inbox", response_model=List[MessageListItem])
async def list_received_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    # Query for messages
    stmt = select(
        Message,
        User.name.label("sender_name"),
        func.count(MessageAttachment.id).label("attachment_count")
    ).join(
        User, Message.sender_id == User.id
    ).outerjoin(
        MessageAttachment, MessageAttachment.message_id == Message.id
    ).where(
        Message.recipient_id == current_user.id
    ).group_by(
        Message.id
    ).order_by(
        desc(Message.created_at)
    ).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    
    # Process results
    messages = []
    for row in result:
        message = row[0]
        message.sender_name = row[1]
        message.has_attachments = row[2] > 0
        messages.append(message)
    
    return messages

# ─────────────────────────────────────────────
# 📤 List sent messages
# ─────────────────────────────────────────────
@router.get("/sent", response_model=List[MessageListItem])
async def list_sent_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    # Query for messages
    stmt = select(
        Message,
        User.name.label("sender_name"),
        func.count(MessageAttachment.id).label("attachment_count")
    ).join(
        User, Message.recipient_id == User.id
    ).outerjoin(
        MessageAttachment, MessageAttachment.message_id == Message.id
    ).where(
        Message.sender_id == current_user.id
    ).group_by(
        Message.id
    ).order_by(
        desc(Message.created_at)
    ).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    
    # Process results
    messages = []
    for row in result:
        message = row[0]
        message.sender_name = current_user.name
        message.has_attachments = row[2] > 0
        messages.append(message)
    
    return messages

# ─────────────────────────────────────────────
# 🔍 Get message details
# ─────────────────────────────────────────────
@router.get("/{message_id}", response_model=MessageOut)
async def get_message_details(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get message with sender and recipient info
    stmt = select(Message).where(
        and_(
            Message.id == message_id,
            (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
        )
    ).options(
        selectinload(Message.sender),
        selectinload(Message.recipient),
        selectinload(Message.attachments)
    )
    
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission")
    
    # Get reactions
    reactions_stmt = select(message_reactions.c.emoji, message_reactions.c.user_id).where(
        message_reactions.c.message_id == message_id
    )
    reactions_result = await db.execute(reactions_stmt)
    reactions_list = reactions_result.all()
    
    # Count reactions by emoji
    message.reactions = count_reactions(reactions_list)
    
    # Mark as read if recipient is viewing
    if not message.is_read and message.recipient_id == current_user.id:
        message.is_read = True
        message.read_at = datetime.now()
        await db.commit()
    
    return message

# ─────────────────────────────────────────────
# 🗑️ Delete a message
# ─────────────────────────────────────────────
@router.delete("/{message_id}", status_code=204)
async def delete_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Find message
    result = await db.execute(select(Message).where(
        and_(
            Message.id == message_id,
            Message.sender_id == current_user.id  # Only senders can delete
        )
    ))
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission")
    
    # Get attachments to delete files
    attachments_result = await db.execute(
        select(MessageAttachment).where(MessageAttachment.message_id == message_id)
    )
    attachments = attachments_result.scalars().all()
    
    # Delete message (will cascade to attachments and reactions)
    await db.delete(message)
    await db.commit()
    
    # Delete attachment files
    for attachment in attachments:
        await delete_attachment(attachment.file_path)
    
    return None