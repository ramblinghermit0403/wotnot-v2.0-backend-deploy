import phonenumbers
from phonenumbers import geocoder, carrier

# Example phone number without country code
phone_number = "4155552671"  # Replace with the actual number

# Try parsing the phone number assuming it's from the default country
# You can iterate over a list of possible countries to get the most likely country

# List of country codes to check against (can be expanded based on the user's needs)
country_codes = ["IN", "US", "GB", "AU", "CA", "DE", "FR", "IT", "BR", "ZA"]  # Add more as needed

for country_code in country_codes:
    try:
        # Parse the phone number assuming it's from a specific country
        parsed_number = phonenumbers.parse(phone_number, country_code)

        # Check if the number is valid
        if phonenumbers.is_valid_number(parsed_number):
            print(f"Country: {geocoder.description_for_number(parsed_number, 'en')}")
            print(f"Country Code: {parsed_number.country_code}")
            print(f"Carrier: {carrier.name_for_number(parsed_number, 'en')}")
            break
    except phonenumbers.phonenumberutil.NumberParseException:
        continue
