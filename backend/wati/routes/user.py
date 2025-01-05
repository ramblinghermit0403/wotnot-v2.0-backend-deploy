from fastapi import APIRouter,Depends,HTTPException,UploadFile,Request
from ..models import User
from ..Schemas import user
from ..database import database
from sqlalchemy.orm import Session
from .. import hashing
import secrets   
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
from ..oauth2 import get_current_user
import httpx
import requests

router=APIRouter(tags=['User'])

@router.post('/register')
async def new_user(
    request: user.register_user,
    db: AsyncSession = Depends(database.get_db),
    get_current_user: user.newuser = Depends(get_current_user)):
    # Check for existing user
    result = await db.execute(
        select(User.User).filter(
            (User.User.email == request.email) | (User.User.Phone_id == request.Phone_id)
        )
    )
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Account with this email or phone number already exists"
        )
    
    # Create a new user
    api_key = secrets.token_hex(32)
    registeruser = User.User( 
        username=request.username,
        email=request.email,
        password_hash=hashing.Hash.bcrypt(request.password),  # Decode the hash to store it as a string
        WABAID=request.WABAID,
        PAccessToken=request.PAccessToken,
        Phone_id=request.Phone_id,
        api_key=api_key
    )
    
    db.add(registeruser)
    await db.commit()  # Commit the transaction asynchronously
    await db.refresh(registeruser)  # Refresh the instance asynchronously

    return {"success": True, "message": "Account created successfully"}


# @router.post("/update-profile", status_code=200)
# async def update_profile(
#     request: user.UpdateProfileRequest,
#     get_current_user: user.newuser = Depends(get_current_user)
# ):
#     # Log request body to see its structure
#     print(request.dict())  # or logging for better handling

#     # ... the rest of your code
@router.post("/update-profile", status_code=200)
def update_profile(
    request: user.BusinessProfile, 
    get_current_user: user.newuser = Depends(get_current_user)
):
    """
    Updates the WhatsApp Business Profile using the provided JSON payload.
    """

    WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{get_current_user.Phone_id}/whatsapp_business_profile"

    # Prepare the request payload by dumping the model and ensuring all fields are serializable
    payload = {
        "messaging_product": request.messaging_product,
        "address": request.address,
        "description": request.description,
        "vertical": request.vertical,
        "about": request.about,
        "email": str(request.email),
        "websites": [str(url) for url in request.websites],
        "profile_picture_url": request.profile_picture_url or None,
    }

    headers = {
        "Authorization": f"Bearer {get_current_user.PAccessToken}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(WHATSAPP_API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            return {"message": "Business profile updated successfully", "data": response.json()}
        else:
            if response.headers.get("Content-Type") == "application/json":
                error_message = response.json().get("error", {}).get("message", "Unknown error occurred")
            else:
                error_message = response.text or "Unknown error occurred"

            raise HTTPException(
                status_code=response.status_code,
                detail=f"{error_message}",
            )

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {e}")




from fastapi import FastAPI, HTTPException, UploadFile
import requests
import mimetypes






@router.post("/resumable-upload/")
async def resumable_upload(file: UploadFile,get_current_user: user.newuser = Depends(get_current_user)):
    # Calculate file parameters
    BASE_URL = "https://graph.facebook.com/v20.0"
    ACCESS_TOKEN = get_current_user.PAccessToken
    file_content = await file.read()
    file_length = len(file_content)  # File size in bytes
    file_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    file_name = file.filename

    # Step 1: Create Upload Session
    create_session_url = f"{BASE_URL}/app/uploads/"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    params = {
        "file_length": file_length,
        "file_type": file_type,
        "file_name": file_name
    }

    create_session_response = requests.post(create_session_url, headers=headers, params=params)
    if create_session_response.status_code != 200:
        raise HTTPException(status_code=create_session_response.status_code, detail=create_session_response.json())

    upload_session_data = create_session_response.json()
    upload_id = upload_session_data["id"]

    # Step 2: Upload File Chunk
    upload_url = f"{BASE_URL}/{upload_id}"
    upload_headers = {
        "Authorization": f"OAuth {ACCESS_TOKEN}",
        'Accept': '*/*',
        'file_offset': str(0)
    }
    

    upload_response = requests.put(upload_url, headers=upload_headers, data=file_content)
    if upload_response.status_code != 200:
        raise HTTPException(status_code=upload_response.status_code, detail=upload_response.json())


    # Step 3: Query Upload Status
    query_url = f"{BASE_URL}/{upload_id}"
    query_response = requests.get(query_url, headers=headers)
    if query_response.status_code != 200:
        raise HTTPException(status_code=query_response.status_code, detail=query_response.json())

    # Combine all results
    return {
        "upload_session": upload_session_data,
        "upload_response": upload_response.json(),
        "query_status": query_response.json()
    }









@router.get("/get-business-profile/")
def get_business_profile(get_current_user: user.newuser = Depends(get_current_user)):
    """
    Fetch the WhatsApp Business Profile details.
    """
    
    BASE_URL = "https://graph.facebook.com/v17.0"
    ACCESS_TOKEN = get_current_user.PAccessToken
    PHONE_NUMBER_ID = get_current_user.Phone_id
    url = f"{BASE_URL}/{PHONE_NUMBER_ID}/whatsapp_business_profile?fields=about,address,description,email,profile_picture_url,websites,vertical"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return response.json()
