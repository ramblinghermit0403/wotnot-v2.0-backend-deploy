from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from .database import database
from .routes import user, broadcast, contacts, auth, woocommerce, integration, wallet
from .services import dramatiq_router
from . import oauth2
from wati.models.ChatBox import Last_Conversation
from .models import ChatBox
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

# Assuming `ChatBox` and `database` are already imported
app = FastAPI()
scheduler = AsyncIOScheduler()

# Models creation



async def create_db_and_tables():
    async with database.engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)



# database.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await create_db_and_tables()

# Adding the routes
app.include_router(broadcast.router)
app.include_router(contacts.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(oauth2.router)
app.include_router(dramatiq_router.router)
app.include_router(woocommerce.router)
app.include_router(integration.router)

# Defining origins for CORS


# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up the schedule
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

scheduler = AsyncIOScheduler()
scheduler_started = False


async def close_expired_chats() -> None:
    """
    Close chats that have been inactive for more than 5 minutes.
    """
    try:
        # Properly acquire an AsyncSession from the generator
        async for session in database.get_db():  # Assuming `get_db` is an async generator
            now = datetime.now()  
            
            # Query for expired conversations
            result = await session.execute(
                select(ChatBox.Last_Conversation).where(
                    ChatBox.Last_Conversation.active == True,
                    now - ChatBox.Last_Conversation.last_chat_time > timedelta(minutes=1440)
                )
            )
            expired_conversations = result.scalars().all()

            # Update the `active` status for each conversation
            for conversation in expired_conversations:
                conversation.active = False
            
            # Commit changes
            await session.commit()

            print(f"Successfully closed {len(expired_conversations)} expired chats.")
            break  # Exit after acquiring the first session

    except Exception as e:
        # Log the error
        print(f"Error in close_expired_chats: {e}")


@app.on_event("startup")
async def startup_event() -> None:
    """
    Event triggered when the application starts.
    Starts the scheduler if not already started.
    """
    global scheduler_started
    if not scheduler_started:
        scheduler.add_job(close_expired_chats, 'interval', minutes=1)
        scheduler.start()
        scheduler_started = True
        print("Scheduler started.")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    Event triggered when the application shuts down.
    Properly stops the scheduler to clean up resources.
    """
    global scheduler_started
    if scheduler_started:
        scheduler.shutdown(wait=False)  # Ensures shutdown is non-blocking
        scheduler_started = False
        print("Scheduler shut down.")
