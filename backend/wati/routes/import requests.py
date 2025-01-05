import requests
import base64
import pandas as pd
import pandas as pd
import phonenumbers
from datetime import datetime,timedelta
import pytz



from datetime import datetime, timedelta
import pytz

def calculate_next_execution_time(repeat_days, time_str):
    """
    Calculate the next execution time based on repeat_days and time in IST.
    """
    # Define IST and UTC timezones
    ist = pytz.timezone('Asia/Kolkata')
    utc = pytz.utc

    # Map days of the week to integers
    days_mapping = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                    "Friday": 4, "Saturday": 5, "Sunday": 6}
    repeat_days = [days_mapping[day] for day in repeat_days]

    # Current time in UTC
    now = datetime.now(utc)
    current_day = now.weekday()
    current_time = now.time()
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Convert target time string (in IST) to UTC
    target_time_ist = datetime.strptime(time_str, "%H:%M")
    target_time_ist = datetime.strptime(f"{current_date} {time_str}", "%Y-%m-%d %H:%M")
    target_time_utc = target_time_ist.astimezone(utc).time()
    print(target_time_utc)

    # Find the next valid day and time
    days_until_next = None
    for day in repeat_days:
        day_difference = (day - current_day) % 7
        if day == current_day and target_time_utc >= current_time:
            days_until_next = day_difference
            break
        elif days_until_next is None or day_difference < days_until_next:
            days_until_next = day_difference

    # Calculate the next execution datetime
    next_date = now + timedelta(days=days_until_next)
    next_execution = datetime.combine(next_date.date(), target_time_utc, tzinfo=utc)

    return next_execution

# Example usage
repeat_days = ["Monday", "Wednesday", "Friday"]
time_str = "23:30"  # Time in IST
next_execution = calculate_next_execution_time(repeat_days, time_str)
print("Next Execution:", next_execution)



# Example date range
start_date = '2024-09-13'
end_date = '2024-12-31'

# Convert the start and end dates to datetime objects
start_date = datetime.strptime(start_date, '%Y-%m-%d')
end_date = datetime.strptime(end_date, '%Y-%m-%d')

# Country codes dictionary
country_code_mapping = {
    "US": "1",
    "IN": "91",
    "GB": "44",
    "AU": "61",
    # Add more country codes here as needed
}

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
            # Remove the4 '+' sign from the formatted number
            return formatted_number.replace('+', '')
        else:
            raise ValueError("Invalid number")
    
    except phonenumbers.phonenumberutil.NumberParseException:
        # If the number is invalid or cannot be parsed, return None
        return None
from urllib.parse import urlparse
# Your WooCommerce API credentials
base_url = "https://go.pixeltests.com/learn/wp-json/wc/v3"
# Parse the URL and extract the hostname
parsed_url = urlparse(base_url)
hostname = parsed_url.hostname


print("Hostname:", hostname)
consumer_key = "ck_9898c473665aecf82609fc08933599b76bf36118"
consumer_secret = "cs_4b542e8e48788b1f8f785ca84bbba53021d587f4"

# Fetch orders
credentials = f"{consumer_key}:{consumer_secret}"
token = base64.b64encode(credentials.encode()).decode()

# Headers
headers = {
    "Authorization": f"Basic {token}",
    "Accept": "*/*",  # Ensures JSON response
    "Cache-Control": "no-cache",   # Mimics Postman's Cache-Control
    "User-Agent": "PostmanRuntime/7.28.0",  # Mimics Postman's User-Agent header
    # "Host": hostname  # Add Host header manually
}

params={
    
    
}

# Fetch orders
response = requests.get(f"{base_url}/orders", headers=headers,params=params)


# Step 1: Decode byte object into string (if needed)


# Step 2: Parse the JSON string into a Python list (or dictionary)
response_data = response.json()
data = []
if response.status_code == 200:
   
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

# Create DataFrame
df = pd.DataFrame(data)
df['phone_no'] = df.apply(lambda row: process_phone_number(row['phone_no'], row['country']), axis=1)


# Convert the 'date' column to datetime type (it is in the 'YYYY-MM-DDTHH:MM:SS' format)
df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%dT%H:%M:%S')

# Filter the DataFrame based on the date range
df_filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

    # Display the processed DataFrame
print(df_filtered)
df_reduced = df[['name', 'phone_no', 'email']]

# Generate list of "name:phone" pairs without quotes
contacts_list = df_reduced.apply(
    lambda row: f"{row['name']}:{row['phone_no']}", axis=1
).tolist()

# Create the final contacts string
name_phone_str = "{" + ",".join(contacts_list) + "}"

recipients = df_reduced.to_json(orient='records')

df_reduced = df_reduced.drop_duplicates(subset='phone_no', keep='first')


print(df_reduced)

integration=[{"key": "billing.first_name"}]
recipient_name="hians"

# if integration:
#                                     body_params = []
#                                     for param in integration:
#                                         # Extract the key from the parameter dictionary
#                                         key = param.get("key")
#                                         # Check if the key is "billing.first_name" and assign the recipient_name
#                                         if key == "billing.first_name":
#                                             body_params.append({"type": "text", "text": recipient_name})
#                                         else:
#                                             # Handle other keys as needed (default empty string here)
#                                             body_params.append({"type": "text", "text": ""})

#                                     if "components" not in data["template"]:
#                                         data["template"]["components"] = []

#                                     data["template"]["components"].append({
#                                         "type": "body",
#                                         "parameters": body_params
#                                     })


