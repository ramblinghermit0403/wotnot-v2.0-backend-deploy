import dramatiq
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dramatiq import Middleware
from ..models import Broadcast,Integration,User  # Adjust this import as needed based on your project structure
import json
from ..routes import contacts
from dramatiq.middleware import Middleware,SkipMessage
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import httpx
from ..models.ChatBox import Conversation
from datetime import datetime
from sqlalchemy.future import select
from dramatiq.middleware import AsyncIO
import asyncio
from datetime import datetime, timedelta
import pytz
from dramatiq.middleware import Middleware
from dramatiq.middleware import SkipMessage
import asyncio
import requests
import base64
import pandas as pd
import pandas as pd
import phonenumbers
from datetime import datetime
from fastapi import HTTPException
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse
import asyncio
import base64
from datetime import datetime
import httpx
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import dramatiq
import json

# SQLAlchemy Database Configuration
SQLALCHEMY_DATABASE_URL = 'postgresql+asyncpg://postgres:Denmarks123$@localhost/wati_clone'

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# @asynccontextmanager
# async def get_db():
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#         finally:
#             await session.close()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
# Base class for declarative models
Base = declarative_base()


# Function to get task status
async def get_task_status(task_id: int, db: AsyncSession):
    """
    Fetches the status of a task based on the task_id from the database.
    """
    result = await db.execute(select(Broadcast.BroadcastList).filter(Broadcast.BroadcastList.task_id == task_id))
    broadcast=result.scalars().first()

    if broadcast:
        return broadcast.status
    
    return "unknown"


class CancelationMiddleware(Middleware):
    def __init__(self, db_session_factory):
        """
        Initialize the middleware with a database session factory.
        
        Args:
            db_session_factory: A callable that provides a database session (e.g., get_db).
        """
        self.db_session_factory = db_session_factory

    def before_process_message(self, broker, message):
        """
        Middleware hook to run before processing a message.

        Args:
            broker: The broker instance.
            message: The message being processed.
        """
        loop = self._get_or_create_event_loop()
        task_status = loop.run_until_complete(self._check_task_status(message.message_id))
        
        if task_status == "Cancelled":
            raise SkipMessage("Task has been cancelled.")

    # async def _check_task_status(self, task_id):
    #     """
    #     Check the status of a task from the database asynchronously.

    #     Args:
    #         task_id: The ID of the task to check.

    #     Returns:
    #         str: The status of the task.
    #     """
    #     async for db in self.db_session_factory():
    #         return await get_task_status(task_id, db)




    async def _check_task_status(self, task_id):
        """
        Check the status of a task from the database asynchronously.

        Args:
            task_id: The ID of the task to check.

        Returns:
            str: The status of the task.
        """
        async for db in self.db_session_factory():# Use async with instead of async for
            return await get_task_status(task_id, db)

        


    @staticmethod
    def _get_or_create_event_loop():
        """
        Get the current event loop, or create a new one if none exists in the current thread.
        
        Returns:
            asyncio.AbstractEventLoop: The event loop for the current thread.
        """
        try:
            return asyncio.get_event_loop()
        except RuntimeError:  # No event loop in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop


cancelation_middleware = CancelationMiddleware(get_db)

# Add the middleware to your Dramatiq broker
from dramatiq.brokers.redis import RedisBroker

redis_broker = RedisBroker(url="redis://localhost:6379")

redis_broker.add_middleware(AsyncIO()) 
redis_broker.add_middleware(cancelation_middleware)
dramatiq.set_broker(redis_broker)




@dramatiq.actor(max_retries=0)
async def send_broadcast(
    template_name,
    template_data, 
    recipients, 
    broadcastId, 
    API_url,
    headers, 
    user_id, 
    image_id, 
    body_parameters,
    Phone_id):
    """
    Dramatiq actor to send broadcast messages.
    """
    db = await anext(get_db())  # Get the db session from the async generator
    try:
        success_count = 0
        failed_count = 0
        errors = []

        async with httpx.AsyncClient() as client:
            for contact in recipients:
                recipient_name = contact["name"]
                recipient_phone = contact["phone"]

                data = {
                    "messaging_product": "whatsapp",
                    "to": recipient_phone,
                    "type": "template",
                    "template": {
                        "name": template_name,
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
                    body_params = [{"type": "text", "text": recipient_name if body_parameters == "Name" else ""}]
                    if "components" not in data["template"]:
                        data["template"]["components"] = []
                    data["template"]["components"].append({
                        "type": "body",
                        "parameters": body_params
                    })

                response = await client.post(API_url, headers=headers, data=json.dumps(data))
                response_data = response.json()

                if response.status_code == 200:
                    success_count += 1
                    wamid = response_data['messages'][0]['id']
                    phone_num = response_data['contacts'][0]["wa_id"]

                    MessageIdLog = Broadcast.BroadcastAnalysis(
                        user_id=user_id,
                        broadcast_id=broadcastId,
                        error_reason="",
                        message_id=wamid,
                        status="sent",
                        phone_no=phone_num,
                        contact_name=recipient_name
                    )
                    db.add(MessageIdLog)
                    await db.commit()
                    await db.refresh(MessageIdLog)

                    # Save the sent message data in conversations table
                    conversation = Conversation(
                        wa_id=recipient_phone,
                        message_id=wamid,
                        media_id="",
                        phone_number_id=Phone_id,
                        message_content=f"#template_message# {template_data}",
                        timestamp=datetime.utcnow(),
                        context_message_id=None,
                        message_type="text",
                        direction="sent"
                    )
                    db.add(conversation)
                    await db.commit()
                    await db.refresh(conversation)


                else:
                    failed_count += 1
                    error_detail = response_data.get("error", {}).get("message", "Unknown error")
                    error_code = response_data.get("error", {}).get("code", "N/A")
                    error_reason = f"Error Code: {error_code}, Detail: {error_detail}"
                
                    errors.append({"recipient": recipient_phone, "error": response_data})
                    
                    MessageIdLog = Broadcast.BroadcastAnalysis(
                        user_id=user_id,
                        broadcast_id=broadcastId,
                        status="failed",
                        phone_no=recipient_phone,
                        contact_name=recipient_name,
                        error_reason=error_reason
                    )
                    db.add(MessageIdLog)
                    await db.commit()
                    await db.refresh(MessageIdLog)

        broadcastLog = await db.get(Broadcast.BroadcastList, broadcastId)
        if not broadcastLog:
            raise Exception(f"Broadcast not found for ID {broadcastId}")

        broadcastLog.success = success_count
        broadcastLog.status = "Successful" if success_count > 0 else "Failed"
        broadcastLog.failed = failed_count

        db.add(broadcastLog)
        await db.commit()
        await db.refresh(broadcastLog)

        if errors:
            print(f"Failed to send some messages: {errors}")
            raise Exception(f"Failed to send broadcast: {errors}")

        print(f"Successfully sent {success_count} messages.")
        
    except Exception as e:
        await db.rollback()  # Rollback in case of an error
        print(f"Error in broadcast: {str(e)}")
        raise e
    finally:
        await db.close()  # Ensure db is closed

   




@dramatiq.actor(max_retries=0)
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
    db = await anext(get_db())
    try:
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
                recipient_name = contact["name"]
                recipient_phone = contact["phone"]

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
                    if "components" not in data["template"]:
                        data["template"]["components"] = []
                    data["template"]["components"].append({
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
                        error_reason="",
                        status="sent",
                        phone_no=phone_num,
                        contact_name=recipient_name,
                    )
                    db.add(message_log)
                    await db.commit()
                    await db.refresh(message_log)

                    # Save the sent message data in conversations table
                    conversation = Conversation(
                        wa_id=recipient_phone,
                        message_id=wamid,
                        media_id="",
                        phone_number_id=phone_id,
                        message_content=f"#template_message# {template_data}",
                        timestamp=datetime.utcnow(),
                        context_message_id=None,
                        message_type="text",
                        direction="sent"
                    )
                    db.add(conversation)
                    await db.commit()
                    await db.refresh(conversation)

                else:
                    failed_count += 1
                    error_detail = response_data.get("error", {}).get("message", "Unknown error")
                    error_code = response_data.get("error", {}).get("code", "N/A")
                    error_reason = f"Error Code: {error_code}, Detail: {error_detail}"

                    errors.append({"recipient": recipient_phone, "error": response_data})

                    message_log = Broadcast.BroadcastAnalysis(
                        user_id=user_id,
                        broadcast_id=broadcast_id,
                        status="failed",
                        phone_no=recipient_phone,
                        contact_name=recipient_name,
                        error_reason=error_reason  # Log error details here
                    )
                    db.add(message_log)
                    await db.commit()
                    await db.refresh(message_log)


        # Update broadcast status
        broadcast = await db.get(Broadcast.BroadcastList,broadcast_id)
        if not broadcast:
            raise Exception(f"Broadcast not found for ID {broadcast_id}")
        broadcast.success = success_count
        broadcast.status = "Successful" if failed_count == 0 else "Partially Successful"
        broadcast.failed = failed_count

        db.add(broadcast)
        await db.commit()
        await db.refresh(broadcast)           

        if errors:
            print(f"Failed to send some messages: {errors}")
            raise Exception(f"Failed to send broadcast: {errors}")
        
        print(f"Successfully sent {success_count} messages.")
        
    except Exception as e:
        await db.rollback()  # Rollback in case of an error
        print(f"Error in broadcast: {str(e)}")
        raise e
    finally:
        await db.close()  # Ensure db is closed




def calculate_next_execution_time(repeat_days, time_str):
    """
    Calculate the next execution time based on repeat_days and time.
    """
    now = datetime.now(pytz.utc)
    current_day = now.strftime("%A")  # Get the current day
    current_time = now.time()

    # Convert time string to a time object
    target_time = datetime.strptime(time_str, "%H:%M").time()

    # Find the next day to run
    days = {day: (i - now.weekday()) % 7 for i, day in enumerate(repeat_days)}
    next_day = min(days, key=lambda x: days[x])  # Get the nearest day

    # Calculate the next run date and time
    days_until_next = days[next_day]
    next_date = now + timedelta(days=days_until_next)
    next_execution = datetime.combine(next_date.date(), target_time, tzinfo=pytz.utc)

    # Adjust for today if time hasn't passed yet
    if days_until_next == 0 and target_time < current_time:
        next_execution += timedelta(days=7)

    return next_execution

def process_phone_number(phone, country_code):
        # Remove spaces, +, - and leading zeros
        phone = ''.join(c for c in phone if c.isdigit())
        phone = phone.lstrip('0')  # Remove leading zeros
        
        try:
            # Try parsing the phone number with the provided country code
            parsed_number = phonenumbers.parse(phone, country_code)
            
            # If the parsed number is valid and has the country code, return it in E164 format
            if phonenumbers.is_valid_number(parsed_number):
                # Get the phone number in international format without the '+' sign
                formatted_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                # Remove the '+' sign from the formatted number
                return formatted_number.replace('+', '')
            else:
                raise ValueError("Invalid number")
        
        except phonenumbers.phonenumberutil.NumberParseException:
            # If the number is invalid or cannot be parsed, return None
            return None
        




# Ensure you're using the correct event loop for asyncio
async def get_event_loop():
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

@dramatiq.actor(max_retries=0)
async def schedule_woo_task(integration_id: int):
    """
    Task to execute the WooCommerce integration and reschedule itself.
    """
    loop = await get_event_loop()
    db = await anext(get_db())  # Ensure we're using the correct event loop
    try:
        # Get the database session
        
            # Fetch integration data
            result = await db.execute(select(Integration.WooIntegration).filter_by(id=integration_id))
            integration = result.scalars().first()

            if not integration:
                print(f"Integration not found: {integration_id}")
                return

            # WooCommerce Integration logic
            base_url = integration.base_url

            # Parse the URL and extract the hostname
            parsed_url = urlparse(base_url)
            hostname = parsed_url.hostname

            consumer_key = integration.rest_key
            consumer_secret = integration.rest_secret

            # Set up authentication and headers
            credentials = f"{consumer_key}:{consumer_secret}"
            token = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {token}",
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "User-Agent": "PostmanRuntime/7.28.0",
                "Host": hostname
            }

            params = {}

            # Use httpx for async HTTP request to fetch WooCommerce orders
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/wp-json/wc/v3/orders", headers=headers, params=params)
                if response.status_code == 200:
                    response_data = response.json()

                    data = []
                    for order in response_data:
                        for item in order['line_items']:
                            data.append({
                                'name': order['billing']['first_name'],
                                'product_id': item['product_id'],
                                'email': order['billing']['email'],
                                'price': item['price'],
                                'phone_no': order['billing']['phone'],
                                'country': order['billing']['country'],
                                'status': order['status'],
                                'date': order['date_created']
                            })

                    # Process and filter data
                    df = pd.DataFrame(data)
                    df['phone_no'] = df.apply(lambda row: process_phone_number(row['phone_no'], row['country']), axis=1)
                    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%dT%H:%M:%S')

                    if integration.contacts_start_date and integration.contacts_end_date:
                        start_date = pd.to_datetime(integration.contacts_start_date)
                        end_date = pd.to_datetime(integration.contacts_end_date)
                        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

                    df_reduced = df[['name', 'phone_no', 'email']]
                    
                    
                    # Remove duplicate entries based on the 'phone_no' column
                    df_reduced = df_reduced.drop_duplicates(subset='phone_no', keep='first')

                    # Generate list of "name:phone" pairs
                    contacts_list = df_reduced.apply(lambda row: f"{row['name']}:{row['phone_no']}", axis=1).tolist()

                    # Add to Broadcast List in the DB
                    db_broadcast_list = Broadcast.BroadcastList(
                        user_id=integration.user_id,
                        name=f"{integration.template}/pwn",
                        template=integration.template,
                        contacts=contacts_list,
                        type="woo/pwn",
                        success=0,
                        failed=0,
                        status="processing",
                    )
                    db.add(db_broadcast_list)
                    await db.commit()
                    await db.refresh(db_broadcast_list)

                    # Send broadcast
                    query = await db.execute(select(User.User).filter(User.User.id == integration.user_id))
                    user = query.scalars().first()

                    if not user:
                        print(f"user not found")


                    image_id = ""
                    recipients = df_reduced.to_json(orient='records')
                    recipients_list = json.loads(recipients) # Convert JSON string to Python list
                    API_url = f"https://graph.facebook.com/v20.0/{user.Phone_id}/messages"

                    success_count = 0
                    failed_count = 0
                    errors = []

                    

                
                    
                async with httpx.AsyncClient() as client:   
                    for contact in recipients_list:
                            recipient_name = contact["name"]
                            recipient_phone = contact["phone_no"]

                            fb_headers = {
                                    "Authorization": f"Bearer {user.PAccessToken}",
                                    "Content-Type": "application/json"
                                }

                            data = {
                                "messaging_product": "whatsapp",
                                "to": recipient_phone,
                                "type": "template",
                                "template": {
                                    "name": integration.template,
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

                            if integration.parameters:
                                for param in integration.parameters:
                                    param_key = param["key"]
                                    
                                    # Map parameter keys to specific values
                                    if param_key == "billing.first_name":
                                        value = recipient_name
                                    # elif param_key == "id":
                                    #     value = order_id
                                    # elif param_key == "total":
                                    #     value = order_total
                                    else:
                                        value = ""  # Default for unknown parameters

                                    # Ensure the components list exists
                                    if "components" not in data["template"]:
                                        data["template"]["components"] = [{"type": "body", "parameters": []}]

                                    # Ensure the first component's parameters list exists
                                    if "parameters" not in data["template"]["components"][0]:
                                        data["template"]["components"][0]["parameters"] = []

                                    # Append the new parameter
                                    data["template"]["components"][0]["parameters"].append({"type": "text", "text": value})



                            # Send the message
                            response = await client.post(API_url, headers=fb_headers, json=data)
                            response_data = response.json()

                            if response.status_code == 200:
                                success_count += 1
                                wamid = response_data['messages'][0]['id']
                                phone_num = response_data['contacts'][0]["wa_id"]

                                # Log success in the database
                                MessageIdLog = Broadcast.BroadcastAnalysis(
                                    user_id=integration.user_id,
                                    broadcast_id=db_broadcast_list.id,
                                    error_reason="",
                                    message_id=wamid,
                                    status="sent",
                                    phone_no=phone_num,
                                    contact_name=recipient_name
                                )
                                db.add(MessageIdLog)
                                await db.commit()
                                await db.refresh(MessageIdLog)

                                # Save conversation data
                                conversation = Conversation(
                                    wa_id=recipient_phone,
                                    message_id=wamid,
                                    media_id="",
                                    phone_number_id=user.Phone_id,
                                    message_content=f"#template_message# {integration.template_data}",
                                    timestamp=datetime.utcnow(),
                                    context_message_id=None,
                                    message_type="text",
                                    direction="sent"
                                )
                                db.add(conversation)
                                await db.commit()
                                await db.refresh(conversation)

                            else:
                                failed_count += 1
                                error_detail = response_data.get("error", {}).get("message", "Unknown error")
                                error_code = response_data.get("error", {}).get("code", "N/A")
                                error_reason = f"Error Code: {error_code}, Detail: {error_detail}"

                                errors.append({"recipient": recipient_phone, "error": response_data})

                                # Log failure in the database
                                MessageIdLog = Broadcast.BroadcastAnalysis(
                                    user_id=user.id,
                                    broadcast_id=db_broadcast_list.id,
                                    status="failed",
                                    phone_no=recipient_phone,
                                    contact_name=recipient_name,
                                    error_reason=error_reason
                                )
                                db.add(MessageIdLog)
                                await db.commit()
                                await db.refresh(MessageIdLog)

                    # Update broadcast log
                    broadcastLog = await db.get(Broadcast.BroadcastList, db_broadcast_list.id)
                    if not broadcastLog:
                        raise Exception(f"Broadcast not found for ID {db_broadcast_list.id}")

                    broadcastLog.success = success_count
                    broadcastLog.status = "Successful" if success_count > 0 else "Failed"
                    broadcastLog.failed = failed_count

                    db.add(broadcastLog)
                    await db.commit()
                    await db.refresh(broadcastLog)

                    if errors:
                        print(f"Failed to send some messages: {errors}")
                        raise Exception(f"Failed to send broadcast: {errors}")

                    print(f"Successfully sent {success_count} messages.")

    except Exception as e:
        await db.rollback()  # Rollback on error
        print(f"Error in broadcast: {str(e)}")
        raise e
    finally:
        await db.close()  # Ensure db is closed