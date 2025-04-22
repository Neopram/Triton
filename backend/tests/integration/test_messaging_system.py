import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.message import Message

# This assumes you have test fixtures for app, client, and db setup

@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, db: AsyncSession, test_user1, test_user2):
    # Log in as user1
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user1.email, "password": "testpassword"}
    )
    token = login_response.json()["access_token"]
    
    # Send message to user2
    message_data = {
        "content": "Hello, this is a test message",
        "recipient_id": test_user2.id
    }
    
    response = await client.post(
        "/api/v1/messages/",
        json=message_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == message_data["content"]
    assert data["sender_id"] == test_user1.id
    assert data["recipient_id"] == test_user2.id
    assert data["is_read"] == False

@pytest.mark.asyncio
async def test_list_inbox(client: AsyncClient, db: AsyncSession, test_user1, test_user2):
    # Create a test message directly in DB
    message = Message(
        sender_id=test_user2.id,
        recipient_id=test_user1.id,
        content="Test inbox message"
    )
    db.add(message)
    await db.commit()
    
    # Log in as user1
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user1.email, "password": "testpassword"}
    )
    token = login_response.json()["access_token"]
    
    # Get inbox
    response = await client.get(
       "/api/v1/messages/inbox",
       headers={"Authorization": f"Bearer {token}"}
   )
   
   assert response.status_code == 200
   data = response.json()
   assert len(data) >= 1
   
   # Find our test message
   test_message = next((m for m in data if m["id"] == message.id), None)
   assert test_message is not None
   assert test_message["content"] == "Test inbox message"
   assert test_message["sender_id"] == test_user2.id

@pytest.mark.asyncio
async def test_message_reactions(client: AsyncClient, db: AsyncSession, test_user1, test_user2):
   # Create a test message directly in DB
   message = Message(
       sender_id=test_user2.id,
       recipient_id=test_user1.id,
       content="Test reaction message"
   )
   db.add(message)
   await db.commit()
   
   # Log in as user1
   login_response = await client.post(
       "/api/v1/auth/login",
       json={"email": test_user1.email, "password": "testpassword"}
   )
   token = login_response.json()["access_token"]
   
   # Add reaction
   response = await client.post(
       f"/api/v1/messages/{message.id}/reactions",
       json={"emoji": "👍"},
       headers={"Authorization": f"Bearer {token}"}
   )
   
   assert response.status_code == 201
   
   # Get message details to check reaction
   response = await client.get(
       f"/api/v1/messages/{message.id}",
       headers={"Authorization": f"Bearer {token}"}
   )
   
   assert response.status_code == 200
   data = response.json()
   assert "👍" in data["reactions"]
   assert data["reactions"]["👍"] == 1
   
   # Remove reaction
   response = await client.delete(
       f"/api/v1/messages/{message.id}/reactions",
       headers={"Authorization": f"Bearer {token}"}
   )
   
   assert response.status_code == 204
   
   # Check reaction was removed
   response = await client.get(
       f"/api/v1/messages/{message.id}",
       headers={"Authorization": f"Bearer {token}"}
   )
   
   data = response.json()
   assert "👍" not in data["reactions"] or data["reactions"]["👍"] == 0