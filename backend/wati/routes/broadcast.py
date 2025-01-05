from fastapi import APIRouter,Depends,HTTPException, File, UploadFile,Request
from fastapi import FastAPI
from ..models import Broadcast,Contacts,ChatBox
from ..models.ChatBox import Last_Conversation
from ..models.ChatBox import Conversation
from ..Schemas import broadcast,user,chatbox
from ..database import database
from sqlalchemy.orm import Session
import json
from fastapi.responses import JSONResponse
import csv
import io
from ..oauth2 import get_current_user
import asyncio
from datetime import datetime
from sqlalchemy import desc
from ..crud.template import send_template_to_whatsapp
from fastapi import APIRouter,Depends,HTTPException, File, UploadFile,Request
from starlette.responses import PlainTextResponse
from ..oauth2 import get_current_user
from ..crud.template import send_template_to_whatsapp# Replace with your actual WhatsApp Business API endpoint and token
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import asyncio
from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import json
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends,Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import asyncio
import json
from sqlalchemy import cast,String
from fastapi import status
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
import httpx
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, cast, String, update,BIGINT
from typing import  AsyncGenerator
from datetime import datetime
import json
import csv
import io
import asyncio
import logging
import httpx
from ..models import Broadcast, Contacts, ChatBox
from ..models.ChatBox import Last_Conversation, Conversation
from ..Schemas import broadcast, user, chatbox
from ..database import database
from ..oauth2 import get_current_user
from ..crud.template import send_template_to_whatsapp




router=APIRouter( tags=['Broadcast'])
app = FastAPI()

WEBHOOK_VERIFY_TOKEN = "12345"  # Replace with your verification token

# Meta Webhook verification endpoint
@router.get("/meta-webhook")
async def verify_webhook(request: Request):
    verify_token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    hubmode = request.query_params.get("hub.mode")
    print(f"Received verify_token: {challenge}, Expected: {WEBHOOK_VERIFY_TOKEN}")
    if verify_token == WEBHOOK_VERIFY_TOKEN and hubmode == "subscribe" :
        return PlainTextResponse(content=request.query_params.get("hub.challenge"),status_code=200)
    
    else:
        raise HTTPException(status_code=403, detail="Verification token mismatch")

# ######### WORKING ENDPOINT WITH BROADCAST REPORT ##########

# POST endpoint to handle webhook data from WhatsApp

@router.post("/meta-webhook")
async def receive_meta_webhook(request: Request, db: AsyncSession = Depends(database.get_db)):
    try:
        # Parse the incoming webhook request
        body = await request.json()
        print(json.dumps(body, indent=4))  # For readability of the incoming payload

        if "entry" not in body:
            raise HTTPException(status_code=400, detail="Invalid webhook format")

        # Process each entry
        for event in body["entry"]:
            if "changes" not in event:
                raise HTTPException(status_code=400, detail="Missing 'changes' key in entry")

            # Iterate through each change
            for change in event["changes"]:
                if "value" not in change:
                    raise HTTPException(status_code=400, detail="Missing 'value' key in changes")

                value = change["value"]

                # Handle messages (replies)
                if "statuses" in value:
                    for status in value["statuses"]:
                        # Check if the necessary keys exist
                        if "recipient_id" not in status or "id" not in status or "status" not in status or "timestamp" not in status:
                            raise HTTPException(status_code=400, detail="Missing keys in statuses")

                        
                        message_status = status["status"]
                        wamid=status['id']

                        message_read=False
                        message_delivered=False
                        message_sent=False
                        error_reason = None
                        

                        
                        if(message_status=="read"):
                            message_read=True
                            message_delivered=True
                            message_sent=True
                            
                        
                        elif(message_status=="delivered"):
                            message_read=False
                            message_delivered=True
                            message_sent=True
                            


                        elif(message_status=="sent"):
                            message_read=False
                            message_delivered=False
                            message_sent=True


                        
                        elif (message_status == "failed"):
                            # Log the error reason from the status
                            if "errors" in status and status["errors"]:
                                error_details = status["errors"][0]
                                error_data_details = status["errors"][0].get("error_data", {}).get("details", "No details available") # Assuming only one error is present
                                error_reason = f"Error Code: {error_details.get('code', 'N/A')}, " \
                                            f"Title: {error_details.get('title', 'N/A')}, " \
                                            f"Details: {error_data_details}"
                            
                                



                        result1 =await db.execute(select(Broadcast.BroadcastAnalysis)
                                .filter( Broadcast.BroadcastAnalysis.message_id==wamid)
                                )
                            
                        broadcast_report=result1.scalars().first()
                        
                        if not broadcast_report:
                                raise HTTPException(status_code=404,detail="Broadcast not found")

                        if wamid:
                                broadcast_report.read=message_read
                                broadcast_report.delivered=message_delivered
                                broadcast_report.sent=message_sent
                                broadcast_report.status=message_status
                                if error_reason is not None:
                                    broadcast_report.error_reason = error_reason 

                        db.add(broadcast_report)
                        await db.commit()
                        await db.refresh(broadcast_report) 
                
                if "messages" in value:
                    
                    for message in value["messages"]:
                        if message.get('context', {}).get('id'):
                            message_reply=True
                            message_status='replied'
                        
                            
                            wamid=message['context']['id']
                            result2 =await db.execute(select(Broadcast.BroadcastAnalysis)
                                    .filter( Broadcast.BroadcastAnalysis.message_id==wamid))
                                
                            broadcast_report=result2.scalars().first()
                            
                            # if not broadcast_report:                                    
                            #         raise HTTPException(status_code=404,detail="Broadcast not found")


                           
                            if broadcast_report:
                                broadcast_report.replied=message_sent=message_reply
                                broadcast_report.status=message_status
                                db.add(broadcast_report)
                                await db.commit()
                                await db.refresh(broadcast_report)
                # Handle incoming messages and replies
                if "messages" in value:
                    await handle_incoming_messages(value, db)


        return {"message": "Webhook data received and processed successfully"}

    except KeyError as e:
        logging.error(f"Missing key in webhook payload: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Missing key: {str(e)}")
    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


async def handle_incoming_messages(value:dict, db: AsyncSession):
# Handle incoming messages
    name = value['contacts'][0]['profile']['name']


    for message in value["messages"]:
        wa_id = message['from']
        phone_number_id = value['metadata']['phone_number_id']
        message_id = message['id']
        message_content = message['text']['body']
        timestamp = int(message['timestamp'])
        message_type = message['type']
        context_message_id = message.get('context', {}).get('id')

        
        utc_time = datetime.utcfromtimestamp(timestamp)


        
        result =await db.execute(select(Last_Conversation).filter(
            Last_Conversation.sender_wa_id == wa_id,
            Last_Conversation.receiver_wa_id == phone_number_id,
            
        ))

        last_conversation=result.scalars().first()

        # Determine if this is the first message in a new conversation

        if last_conversation:
            # Clear previous expired conversations for this pair

            await db.delete(last_conversation)
            await db.commit()


        last_Conversation = Last_Conversation(
                business_account_id=value['metadata'].get('business_account_id', 'unknown'),
                message_id=message_id,
                message_content=message_content,
                sender_wa_id=wa_id,
                sender_name=name,
                receiver_wa_id=phone_number_id,
                last_chat_time=utc_time,
                active=True
            )
        db.add(last_Conversation)
        await db.commit()

        # Store the message in the Conversations table
        conversation = Conversation(
            wa_id=wa_id,
            message_id=message_id,
            phone_number_id=int(phone_number_id),
            message_content=message_content,
            timestamp=utc_time,
            context_message_id=context_message_id,
            message_type=message_type,
            direction="Receive"
        )
        db.add(conversation)
        await db.commit()


from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import asyncio
import json
from typing import AsyncGenerator


@router.get("/sse/conversations/{contact_number}")
async def event_stream(
    contact_number: str,
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Query(...),
    db: AsyncSession = Depends(database.get_db), # Use AsyncSession for async DB operations
) -> StreamingResponse:

    current_user = await get_current_user(token, db)
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    async def get_conversations() -> AsyncGenerator[str, None]:
        last_data = None  # Track last conversation data

        # Send an empty initial response to avoid frontend timeouts

        while True:
            async with db.begin():  # Use async context manager to handle the session
                # Fetch conversations for the given contact number
                result = await db.execute(
                    select(ChatBox.Conversation)
                    .filter(ChatBox.Conversation.wa_id == contact_number).filter(ChatBox.Conversation.phone_number_id==current_user.Phone_id)
                    .order_by(ChatBox.Conversation.timestamp)
                )
                conversations = result.scalars().all()  # Get the list of conversation instances

            # Convert conversation instances to dictionaries
            conversation_data = [convert_to_dict(conversation) for conversation in conversations]

            # Send data only if it has changed
            if conversation_data != last_data:
                yield f"data: {json.dumps(conversation_data)}\n\n"
                last_data = conversation_data  # Update the last known data

            # Check if the client is disconnected
            if await request.is_disconnected():
                break

            # Wait for a second before checking again
            await asyncio.sleep(2)

    return StreamingResponse(get_conversations(), media_type="text/event-stream")



def convert_to_dict(instance):
    """Convert SQLAlchemy model instance to a dictionary."""
    if instance is None:
        return None
    
    instance_dict = {}
    for key, value in instance.__dict__.items():
        if not key.startswith('_'):
            # Check if the value is a datetime instance
            if isinstance(value, datetime):
                instance_dict[key] = value.isoformat()  # Convert to string
            else:
                instance_dict[key] = value
    
    return instance_dict
# Assuming `ChatBox`, `database`, and `convert_to_dict` are defined elsewhere




@router.get("/active-conversations")
async def get_active_conversations(
    token: str = Query(...),
    db: AsyncSession = Depends(database.get_db),  # Use AsyncSession for async DB operations
) -> StreamingResponse:
    # Authenticate the user using the token
    current_user = await get_current_user(token, db)
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    async def get_active_chats() -> AsyncGenerator[str, None]:
        last_active_chats = None  # Variable to hold the last known state of active chats
        
        while True:
            # Asynchronously query the database for active chats
            result = await db.execute(
                select(ChatBox.Last_Conversation)
                .filter(cast(ChatBox.Last_Conversation.receiver_wa_id, String) == str(current_user.Phone_id)).order_by(desc(ChatBox.Last_Conversation.last_chat_time))
            )
            
            # Fetch results and convert to a list of dictionaries
            active_chat_data = [convert_to_dict(chat) for chat in result.scalars().all()]

            # Check if the current active chats are different from the last known state
            if active_chat_data != last_active_chats:
                # Update the last known state
                last_active_chats = active_chat_data
                # Yield the updated active chats as a JSON string
                yield f"data: {json.dumps(active_chat_data)}\n\n"

            # Sleep for a while before the next check
            await asyncio.sleep(1)  # Use await with asyncio.sleep for non-blocking sleep

    return StreamingResponse(get_active_chats(), media_type="text/event-stream")






@router.post("/send-text-message-reply/")
async def send_message(
    payload: chatbox.MessagePayload,
    db: AsyncSession = Depends(database.get_db),  # Use async db dependency
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Construct the URL for sending the message
    whatsapp_url = f"https://graph.facebook.com/v20.0/{get_current_user.Phone_id}/messages"

    # Set up headers with the access token provided by the frontend
    headers = {
        "Authorization": f"Bearer {get_current_user.PAccessToken}",
        "Content-Type": "application/json"
    }

    # Construct the message payload to be sent to the WhatsApp Business API


    data={
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": payload.wa_id,
    "context": {
        "message_id": payload.context_message_id
    },
    "type": "text",
    "text": {
        "preview_url": False,
        "body": payload.body
    }
}

    async with httpx.AsyncClient() as client:
        # Send POST request to WhatsApp API
        response = await client.post(whatsapp_url, headers=headers, json=data)

    # Check for errors in the response
    if response.status_code != 200:
        print(response.json())
        raise HTTPException(status_code=response.status_code, detail=response.json())

    # Parse the response JSON to get message details
    response_data = response.json()

    try:
        # Save the sent message data in conversations table
        conversation = Conversation(
            wa_id=payload.wa_id,
            message_id=response_data.get("messages")[0].get("id"),
            phone_number_id=get_current_user.Phone_id,
            message_content=payload.body,
            timestamp=datetime.utcnow(),
            context_message_id=payload.context_message_id,  # Set based on your needs
            message_type="text",
            direction="sent"  # Set direction to "sent"
        )

        db.add(conversation)
        await db.commit()  # Commit changes asynchronously
        await db.refresh(conversation)  # Refresh asynchronously

        return {"status": "Message sent", "response": response_data}

    except Exception as e:
        await db.rollback()  # Rollback in case of any error asynchronously
        print(f"Error storing message in conversation table: {e}")
        raise HTTPException(status_code=500, detail="Error storing message in database")

@router.post("/send-text-message/")
async def send_message(
    payload: chatbox.MessagePayload,
    db: AsyncSession = Depends(database.get_db),  # Use async db dependency
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Construct the URL for sending the message
    whatsapp_url = f"https://graph.facebook.com/v20.0/{get_current_user.Phone_id}/messages"

    # Set up headers with the access token provided by the frontend
    headers = {
        "Authorization": f"Bearer {get_current_user.PAccessToken}",
        "Content-Type": "application/json"
    }

    # Construct the message payload to be sent to the WhatsApp Business API
    data = {
        "messaging_product": "whatsapp",
        "to": payload.wa_id,
        "type": "text",
        "text": {
            "body": payload.body
        }
    }

    async with httpx.AsyncClient() as client:
        # Send POST request to WhatsApp API
        response = await client.post(whatsapp_url, headers=headers, json=data)

    # Check for errors in the response
    if response.status_code != 200:
        print(response.json())
        raise HTTPException(status_code=response.status_code, detail=response.json())

    # Parse the response JSON to get message details
    response_data = response.json()

    try:
        # Save the sent message data in conversations table
        conversation = Conversation(
            wa_id=payload.wa_id,
            message_id=response_data.get("messages")[0].get("id"),
            phone_number_id=get_current_user.Phone_id,
            message_content=payload.body,
            timestamp=datetime.utcnow(),
            context_message_id=None,  # Set based on your needs
            message_type="text",
            direction="sent"  # Set direction to "sent"
        )

        db.add(conversation)
        await db.commit()  # Commit changes asynchronously
        await db.refresh(conversation)  # Refresh asynchronously

        return {"status": "Message sent", "response": response_data}

    except Exception as e:
        await db.rollback()  # Rollback in case of any error asynchronously
        print(f"Error storing message in conversation table: {e}")
        raise HTTPException(status_code=500, detail="Error storing message in database")

import dramatiq
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime
import httpx


@router.post("/send-template-message/")
async def send_template_message(
    request: broadcast.input_broadcast,
    get_current_user: user.newuser = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    # Save broadcast details
    print(request.template)
    broadcast_list = Broadcast.BroadcastList(
        user_id=get_current_user.id,
        name=request.name,
        template=request.template,
        contacts=[contact.phone for contact in request.recipients],  # Only storing phone numbers for now
        type=request.type,
        success=0,
        failed=0,
        status="processing..."
    )
    db.add(broadcast_list)
    await db.commit()
    await db.refresh(broadcast_list)


    contacts = [{"name": contact.name, "phone": contact.phone} for contact in request.recipients]
    # Start the background task
    send_template_messages_task.send(
        broadcast_id=broadcast_list.id,
        recipients=contacts,
        template=request.template,
        template_data=request.template_data,
        image_id=request.image_id,
        body_parameters=request.body_parameters,
        phone_id=get_current_user.Phone_id,
        access_token=get_current_user.PAccessToken,
        user_id=get_current_user.id
    )

    return {"status": "processing", "broadcast_id": broadcast_list.id}


@dramatiq.actor
async def send_template_messages_task(
    broadcast_id: int,
    recipients: list,
    template: str,
    template_data:str,
    image_id: str,
    body_parameters: str,
    phone_id: str,
    access_token: str,
    user_id: int,
):


    async with database.get_db() as db:
        success_count = 0
        failed_count = 0
        errors = []
        
        API_url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }


        async with httpx.AsyncClient() as client:
            for contact in recipients:
                recipient_name = contact.name
                recipient_phone = contact.phone



                data = {
                    "messaging_product": "whatsapp",
                    "to": recipient_phone,
                    "type": "template",
                    "template": {
                        "name": template,
                        "language": {"code": "en_US"},
                    }
                }

                if image_id:
                    data["template"]["components"] = [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "image": {"id": image_id}
                                }
                            ]
                        }
                    ]

                if body_parameters:
                    body_params = [{"type": "text", "text": f"{recipient_name}"}] if body_parameters == "Name" else []
                    data["template"].setdefault("components", []).append({
                        "type": "body",
                        "parameters": body_params
                    })

                response = await client.post(API_url, headers=headers, json=data)
                response_data = response.json()

                if response.status_code == 200:
                    success_count += 1
                    wamid = response_data['messages'][0]['id']
                    phone_num = response_data['contacts'][0]["wa_id"]

                    message_log = Broadcast.BroadcastAnalysis(
                        user_id=user_id,
                        broadcast_id=broadcast_id,
                        message_id=wamid,
                        status="sent",
                        phone_no=phone_num,
                        contact_name=recipient_name,
                    )
                    db.add(message_log)

                    # Save the sent message data in conversations table
                    conversation = Conversation(
                        wa_id=recipient_phone,
                        message_id=wamid,
                        phone_number_id=phone_id,
                        message_content=f"#template_message# {template_data}",
                        timestamp=datetime.utcnow(),
                        context_message_id=None,
                        message_type="text",
                        direction="sent"
                    )
                    db.add(conversation)

                else:
                    failed_count += 1
                    errors.append({"recipient": recipient_phone, "error": response_data})

                    message_log = Broadcast.BroadcastAnalysis(
                        user_id=user_id,
                        broadcast_id=broadcast_id,
                        status="failed",
                        phone_no=recipient_phone,
                        contact_name=recipient_name,
                    )
                    db.add(message_log)

        # Commit all changes in one go after the loop
        await db.commit()

        # Update broadcast status
        result = await db.execute(
            select(Broadcast.BroadcastList).filter(Broadcast.BroadcastList.id == broadcast_id)
        )
        broadcast = result.scalars().first()
        if broadcast:
            broadcast.success = success_count
            broadcast.status = "Successful" if failed_count == 0 else "Partially Successful"
            broadcast.failed = failed_count
            await db.commit()


@router.get("/templates")
async def get_templates(get_current_user: user.newuser = Depends(get_current_user)):
    API_URL = f'https://graph.facebook.com/v15.0/{get_current_user.WABAID}/message_templates'
    headers = {
        'Authorization': f'Bearer {get_current_user.PAccessToken}'
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    # Extract template names
    template_names = [template['name'] for template in data.get('data', [])]
    return JSONResponse(content=template_names)


@router.post("/broadcast")
async def broadcastList(
    request: broadcast.BroadcastListCreate,
    db: AsyncSession = Depends(database.get_db),
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Create a new Broadcast instance
    broadcastList = Broadcast.BroadcastList(
        user_id=get_current_user.id,
        name=request.name,
        template=request.template,
        contacts=request.contacts,
        type=request.type,
        success=request.success,
        failed=request.failed,
        status=request.status,
        scheduled_time=request.scheduled_time,
        task_id=request.task_id
    )
    
    # Add the new broadcast to the session
    db.add(broadcastList)

    # Commit the changes asynchronously
    await db.commit()

    # Refresh the instance with updated data
    await db.refresh(broadcastList)

    # Return the ID of the newly created broadcast
    return {
        "broadcast_id": broadcastList.id
    }



@router.post("/broadcast", response_model=dict)
async def broadcastList(
    request: broadcast.BroadcastListCreate,
    db: Session = Depends(database.get_db),
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Initialize success and failed counts
    success_count = 0
    failed_count = 0

    # Create the BroadcastList instance
    broadcast_list = Broadcast.BroadcastList(
        user_id=get_current_user.id,
        name=request.name,
        template=request.template,
        contacts=request.contacts,
        type=request.type,
        success=success_count,  # Initial success count
        failed=failed_count,    # Initial failed count
        status="processing",     # Initial status
        scheduled_time=request.scheduled_time,
        task_id=request.task_id
    )

    try:
        db.add(broadcast_list)
        db.commit()
        db.refresh(broadcast_list)

        return {
            "broadcast_id": broadcast_list.id
        }
    except Exception as e:
        db.rollback()  # Rollback the session on error
        raise HTTPException(status_code=500, detail=str(e))
    
    
# Route to fetch the broadcastlist
@router.get('/broadcast')  # Use your response model here
async def fetchbroadcastList(
    limit: int = Query(10),
    offset: int = Query(0),
    statusfilter: str | None = Query(None),
    tag: str | None = Query(None),
    db: AsyncSession = Depends(database.get_db),  # Ensure this is your async db session dependency
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Start building the query
   

    query = select(Broadcast.BroadcastList).filter(Broadcast.BroadcastList.user_id == get_current_user.id).order_by(desc(Broadcast.BroadcastList.id))


    # Apply tag filtering if provided
    if tag:
        query = query.filter(Broadcast.BroadcastList.template.ilike(f"%{tag}%")) # Adjust field as needed

    if statusfilter!="null" :
        query=query.filter(Broadcast.BroadcastList.status==statusfilter)
    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute the query
    result = await db.execute(query)
    broadcast_list = result.scalars().all()

    # Check if any broadcasts were found
    if not broadcast_list:
        raise HTTPException(status_code=404, detail="No broadcasts found")

    return broadcast_list





@router.put("/broadcast/{broadcast_id}")
async def update_broadcast(
    broadcast_id: int,
    broadcast_update: broadcast.BroadcastListUpdate,
    db: AsyncSession = Depends(database.get_db),
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Retrieve the broadcast entry from the database
    result = await db.execute(
        select(Broadcast.BroadcastList).where(Broadcast.BroadcastList.id == broadcast_id)
    )
    broadcast = result.scalar_one_or_none()

    # If the broadcast entry does not exist, raise an HTTP 404 error
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    # Update the broadcast entry with new data
    if broadcast_update.task_id:
        broadcast.task_id = broadcast_update.task_id

    # Commit the changes to the database
    db.add(broadcast)  # Not strictly necessary; you can also just modify the object directly
    await db.commit()  # Commit changes asynchronously
    await db.refresh(broadcast)  # Refresh the instance with updated data

    # Return the updated broadcast entry
    return {
        "message": "Broadcast updated successfully",
        "broadcast_id": broadcast_id,
        "task_id": broadcast.task_id
    }




@router.get("/scheduled-broadcast")
async def fetch_scheduled_broadcast_list(
    skip: int = 0, limit: int = 10, tag: str = None, 
    db: AsyncSession = Depends(database.get_db),
    get_current_user: user.newuser = Depends(get_current_user)
):
    query = select(Broadcast.BroadcastList).where(
        Broadcast.BroadcastList.status == "Scheduled"
    ).order_by(Broadcast.BroadcastList.id.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    scheduled_broadcast_list = result.scalars().all()
    
    return scheduled_broadcast_list
   

@router.post("/import-contacts")
async def import_contacts(file: UploadFile = File(...), db: AsyncSession = Depends(database.get_db)):
    # Read the file contents asynchronously
    contents = await file.read()
    
    # Decode and parse CSV contents
    try:
        reader = csv.DictReader(io.StringIO(contents.decode("utf-8")))
        contacts = []
        for row in reader:
            contact = Contacts.Contact(name=row['name'], phone=row['phone'])
            contacts.append(contact)

        # Optionally add to database here
        # db.bulk_save_objects(contacts)
        # db.commit()

    except Exception as e:
        raise HTTPException(status_code=400, detail="Error reading or parsing CSV file.")
    
    return {"contacts": contacts}


@router.get("/template")
async def get_templates(get_current_user: user.newuser = Depends(get_current_user)):
    API_URL = f'https://graph.facebook.com/v15.0/{get_current_user.WABAID}/message_templates'
    headers = {
        'Authorization': f'Bearer {get_current_user.PAccessToken}'
    }

    # Make an asynchronous HTTP GET request
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, headers=headers)
    
    # Check for errors in the API response
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    return data




@router.delete("/broadcasts-delete/{broadcast_id}")
async def delete_scheduled_broadcast(
    broadcast_id: int,
    db: AsyncSession = Depends(database.get_db),
    get_current_user: user.newuser = Depends(get_current_user)
):
    # Fetch the broadcast asynchronously
    result = await db.execute(
        select(Broadcast.BroadcastList).filter(Broadcast.BroadcastList.id == broadcast_id)
    )
    broadcast = result.scalars().first()

    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    
    # Update the status to 'Cancelled' asynchronously
    broadcast.status = "Cancelled"
    await db.commit()
    
    return {"detail": "Scheduled broadcast has been canceled."}


@router.post("/create-template", response_model=broadcast.TemplateResponse)
async def create_template(
    template: broadcast.TemplateCreate,
    request: Request,
    get_current_user: user.newuser = Depends(get_current_user)
):
    try:
        template_data = await request.json()  # Await JSON data from the request
        broadcast.TemplateCreate.validate_template(template_data)  # Ensure the template is validated synchronously
        
        # Send the template asynchronously to WhatsApp
        response = await send_template_to_whatsapp(
            template_data,
            get_current_user.PAccessToken,
            get_current_user.WABAID
        )
        
        return response
    except HTTPException as e:
        logging.critical(f"HTTP Exception: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logging.critical(f"Unexpected Exception: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.delete("/delete-template/{template_name}")
async def DeleteTemplate(   
    template_name:str,
    request: Request,
    get_current_user: user.newuser = Depends(get_current_user)):

        url = f"https://graph.facebook.com/v14.0/{get_current_user.WABAID}/message_templates?name={template_name}"
        headers = {
            "Authorization": f"Bearer {get_current_user.PAccessToken}",
            "Content-Type": "application/json"
        }


        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        
        return {"Template deleted successfully"}


@router.get("/broadcast-report/{broadcast_id}")
async def BroadcastReport(
    broadcast_id: int,
    get_current_user: user.newuser = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):

    query = select(Broadcast.BroadcastAnalysis).filter(
        (Broadcast.BroadcastAnalysis.user_id == get_current_user.id) &
        (Broadcast.BroadcastAnalysis.broadcast_id == broadcast_id)
    )
    
    result = await db.execute(query)
    broadcast_data = result.scalars().all()

    if not broadcast_data:
        raise HTTPException(status_code=404, detail="Broadcast data not found")

    return broadcast_data

@router.post("/upload-media")
async def upload_file(
    file: UploadFile = File(...),
    get_current_user: user.newuser = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    # Read the contents of the uploaded file
    try:
        contents = await file.read()
    except Exception as e:
        logging.error(f"Error reading uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Invalid file upload.")
    
    # Define the media upload URL and headers
    media_url = f"https://graph.facebook.com/v20.0/{get_current_user.Phone_id}/media"
    headers = {
        "Authorization": f"Bearer {get_current_user.PAccessToken}"
    }

    # Prepare the multipart/form-data payload
    multipart_data = {
        'type': file.content_type.split("/")[0],  # Extract media type (e.g., image, video)
        'messaging_product': 'whatsapp'
    }
    
    # httpx expects files in a specific format for multipart uploads
    files = {
        'file': (file.filename, contents, file.content_type)
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                media_url,
                headers=headers,
                files=files,
                data=multipart_data,
                timeout=60.0  # Optional: Set a timeout for the request
            )
        
        # Parse the JSON response
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response from WhatsApp API.")
            raise HTTPException(status_code=502, detail="Invalid response from WhatsApp API.")
        
        # Check for errors in the WhatsApp API response
        if response.status_code != 200:
            error_detail = response_data.get("error", {}).get("message", "Unknown error")
            logging.error(f"WhatsApp API error: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        # Get the media ID from the response
        media_id = response_data.get("id")
        if not media_id:
            logging.error("Media ID not found in WhatsApp API response.")
            raise HTTPException(status_code=502, detail="Media ID not returned by WhatsApp API.")
        

        return JSONResponse(content={
            "filename": file.filename,
            "file_size": len(contents),
            "content_type": file.content_type,
            "whatsapp_media_id": media_id
        })
    
    except httpx.RequestError as e:
        logging.error(f"HTTP request failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to WhatsApp API.")
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP status error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while uploading the media.")



from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
import requests
import mimetypes



# Configuration for the API


@router.get("/download-media/{media_id}")
async def load_media(
    media_id: str,  # Media ID from the client
    get_current_user: user.newuser = Depends(get_current_user),  # User validation
    db: AsyncSession = Depends(database.get_db)  # Database session
):
    """
    Downloads media from WhatsApp using its media ID and serves it to the client.
    """
    try:
        # Step 1: Get the media URL
        response = requests.get(
            f"https://graph.facebook.com/v20.0/{media_id}",
            headers={"Authorization": f"Bearer {get_current_user.PAccessToken}"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Media not found")

        media_url = response.json().get("url")
        if not media_url:
            raise HTTPException(status_code=404, detail="Unable to retrieve media URL")

        # Step 2: Download the media
        media_response = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {get_current_user.PAccessToken}"}
        )

        if media_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to download media")

        # Determine the MIME type from the response headers
        content_type = media_response.headers.get("Content-Type", "application/octet-stream")
        extension = mimetypes.guess_extension(content_type) or ".bin"  # Default to binary if unknown

        # Serve the media file as a response
        return Response(
            content=media_response.content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=downloaded_media{extension}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    




