import telepot
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.loop import MessageLoop
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
from threading import Timer
from settings import TG_TOKEN, CAL_TOKEN, SHEETS_TOKEN,SHEETS_ID
TG_TOKEN = TG_TOKEN
CAL_TOKEN="credentials_calendar.json"
SHEETS_TOKEN="credentials_sheets.json"

sheet_scope = ["https://www.googleapis.com/auth/spreadsheets"]

def write_to_google_sheets(user_info, selected_service, slot_number, start_time):
    # Load credentials from the token.json file or create them if it doesn't exist.
    creds = None
    if os.path.exists('google_sheets_token.json'):
        creds = Credentials.from_authorized_user_file('google_sheets_token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                SHEETS_TOKEN, sheet_scope)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_sheets_token.json', 'w') as token:
            token.write(creds.to_json())

    # Create a service using the credentials
    service = build('sheets', 'v4', credentials=creds)

    # Spreadsheet ID for your Google Sheets document
    spreadsheet_id = SHEETS_ID

    # Determine which sheet to write to based on the selected service
    sheet_name = 'Sheet1' if selected_service == "Hair Salon and Beauty Parlour" else 'Sheet2'

    # Construct the range to write to (modify this based on your sheet structure)
    range_to_write = f"{sheet_name}!A:E"

    # Prepare the values to be written
    new_entry = [user_info.get('name', ''), user_info.get('phone', ''), slot_number, start_time.strftime('%d-%m-%Y'), start_time.strftime('%H:%M')]

    # Load existing values from the sheet
    existing_values_result = existing_values(service, spreadsheet_id, range_to_write)
    values = existing_values_result if existing_values_result else []

    # Append the new entry to the existing values
    values.append(new_entry)

    values = [row for row in values if len(row) == 5 and row[3] != 'DATE']
    # Sort the values based on the date and time (assuming date is in index 3 and time is in index 4)
    values.sort(key=lambda x: (datetime.strptime(x[3], '%d-%m-%Y'), datetime.strptime(x[4], '%H:%M')))

    # Write the sorted values to the sheet
    write_values(service, spreadsheet_id, range_to_write, values)

    # Schedule the slot to be erased after the end time
    end_time = start_time + slot_duration
    schedule_slot_erase(service, spreadsheet_id, sheet_name, slot_number, end_time)




def existing_values(service, spreadsheet_id, range_to_read):
    # Read values from the sheet
    request = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_to_read,
    )
    response = request.execute()
    return response.get('values', [])

def write_values(service, spreadsheet_id, range_to_write, values):
    # Write the values to the sheet
    request = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_to_write,
        valueInputOption='RAW',
        body={'values': values}
    )
    response = request.execute()




def schedule_slot_erase(service, spreadsheet_id, sheet_name, slot_number, end_time):
    # Calculate the delay until the end time
    delay_seconds = (end_time - datetime.utcnow()).total_seconds()

    # Schedule the slot erase
    Timer(delay_seconds, erase_slot, args=(service, spreadsheet_id, sheet_name, slot_number)).start()


def clear_booked_slots():
    global booked_slots_hair_beauty, booked_slots_spa_wellbeing

    # Get the current date
    current_date = datetime.now().date()

    # Check if a new day has started
    if current_date > clear_booked_slots.last_cleared_date:
        # Clear booked slots lists
        booked_slots_hair_beauty = []
        booked_slots_spa_wellbeing = []

        # Update the last cleared date
        clear_booked_slots.last_cleared_date = current_date

# Set the initial last cleared date
clear_booked_slots.last_cleared_date = datetime.now().date()



def erase_slot(service, spreadsheet_id, sheet_name, slot_number):
    # Load credentials from the token.json file or create them if it doesn't exist.
    creds = None
    if os.path.exists('google_sheets_token.json'):
        creds = Credentials.from_authorized_user_file('google_sheets_token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', ['https://www.googleapis.com/auth/spreadsheets']
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_sheets_token.json', 'w') as token:
            token.write(creds.to_json())

    # Create a service using the credentials
    service = build('sheets', 'v4', credentials=creds)

    # Get the sheet ID based on the sheet name
    sheets_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheets_metadata.get('sheets', '')
    sheet_id = None
    for sheet in sheets:
        if sheet['properties']['title'] == sheet_name:
            sheet_id = sheet['properties']['sheetId']
            break

    if sheet_id is None:
        print(f"Sheet with name {sheet_name} not found.")
        return

    # Construct the range to delete from (modify this based on your sheet structure)
    range_to_delete = f"{sheet_name}!A:E"

    # Find and delete the row with the specified slot number
    request = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_to_delete,
    )
    response = request.execute()
    values = response.get('values', [])

    if values:
        for i, row in enumerate(values):
            if len(row) > 2 and int(row[2]) == slot_number:  # Assuming the slot number is in column C
                # Delete the row
                request = service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        'requests': [
                            {
                                'deleteDimension': {
                                    'range': {
                                        'sheetId': sheet_id,
                                        'dimension': 'ROWS',
                                        'startIndex': i,
                                        'endIndex': i + 1,
                                    },
                                },
                            },
                        ],
                    },
                )
                response = request.execute()
                print(f"Slot {slot_number} erased from {sheet_name} sheet: {response}")
                break





# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_calendar():
    creds = None
    token_path = 'token.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CAL_TOKEN, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    print("Authentication successful")
    return creds

def create_calendar_event(credentials, service, user_id, selected_service, slot_number, start_time, end_time, bot):
    event = {
        'summary': f'Booking - {selected_service}',
        'description': f'Slot {slot_number} for {selected_service}',
        'start': {
            'dateTime': start_time.isoformat() + 'Z',
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat() + 'Z',
            'timeZone': 'UTC',
        },
    }

    try:
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        event_id = created_event['id']
        event_link = f'https://www.google.com/calendar/event?eid={event_id}'

        print(f'Event created with ID: {event_id}')
        print(f'Event link: {event_link}')

        bot.sendMessage(user_id, f"Slot {slot_number} for {selected_service} on {start_time.strftime('%A, %Y-%m-%d')} "
                                   f"from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')} has been booked."
                                   f"\nThank you! Your slot has been confirmed.")

        return created_event
    except Exception as e:
        error_message = f'Error creating Google Calendar event: {e}'
        print(error_message)
        bot.sendMessage(user_id, f'Error booking the slot. Please try again later. Error: {e}')

    return None





booked_slots_hair_beauty = []
booked_slots_spa_wellbeing = []
slot_duration = timedelta(hours=2)

def generate_slots(selected_service):
    # Initialize a dictionary to store slots for each day
    slots_by_day = {}

    # Get the current date
    current_date = datetime.now()

    # Generate slots for the next seven days
    for day in range(7):
        # Calculate the date for the current iteration
        current_day = current_date + timedelta(days=day)

        # Initialize slots for the current day
        slots_by_day[current_day] = []

        # Generate two slots for each service
        for slot_number in range(1, 3):
            # Calculate start time for the slot
            start_time = current_day.replace(hour=slot_number * 2, minute=0, second=0)

            # Calculate end time for the slot
            end_time = start_time + slot_duration

            # Assign a unique slot number
            unique_slot_number = (day * 2) + slot_number

            # Check if the slot is booked for the selected service
            if (selected_service == "Hair Salon and Beauty Parlour" and unique_slot_number in booked_slots_hair_beauty) or \
               (selected_service == "Spa and Wellbeing" and unique_slot_number in booked_slots_spa_wellbeing):
                continue  # Skip booked slots

            # Add the slot to the list for the current day
            slots_by_day[current_day].append({
                'unique_slot_number': unique_slot_number,
                'start_time': start_time,
                'end_time': end_time
            })

    return slots_by_day


def display_available_slots(user_id, selected_service, available_slots):
    # Display available slots to the user
    bot.sendMessage(user_id, f"Available slots for {selected_service} in the next seven days:")

    for day, slots in available_slots.items():
        bot.sendMessage(user_id, f"\n{day.strftime('%A, %Y-%m-%d')}:")
        for slot in slots:
            start_time_str = slot['start_time'].strftime('%H:%M')
            end_time_str = slot['end_time'].strftime('%H:%M')
            bot.sendMessage(user_id, f"Slot {slot['unique_slot_number']}: {start_time_str} to {end_time_str}")

    # Prompt the user to enter the desired slot number
    bot.sendMessage(user_id, "Please enter the slot number you'd like to book:", reply_markup={'force_reply': True})



# Dictionary to store user information
user_data = {}

def handle_start(chat_id, text):
    """Send a welcome message when the command /start is issued."""
    if text == '/start':
        bot.sendMessage(
            chat_id,
            "Hi! Welcome to the Appointment Fixer Bot. "
            "To get started, please go through the available commands using /help."
        )
    elif text == '/help':
        bot.sendMessage(
            chat_id,
            'Hi! I am here to help you :-)\n'
            'Send me a message to start.\n'
            'Use /menu command to get the list of services available\n'
            'Use /book command to book a slot.\n'
            'Use /exist to check about the already booked upcoming slots.\n'
            'Use /help if you have any concern.\n'
            'Finally, a /bye would be great.'
        )

def handle_messages(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)

    if content_type == 'text':
        text = msg['text']
        user_id = msg['from']['id']

        if text == '/start' or text == '/help':
            handle_start(chat_id, text)

        elif text == '/book':
            # Set the user's state to 'get_name' to start the process
            user_data[user_id] = {'state': 'get_name'}
            # Send a message with an input field for the user to enter their name
            bot.sendMessage(user_id, 'Please enter your name:', reply_markup={'force_reply': True})

        elif text == '/exist':
            handle_exist_command(user_id)
    
        elif text == '/cancel':
            if user_id in user_data and 'state' in user_data[user_id] and     user_data[user_id]['state'] == 'cancel_booking':
                # Extract booking information from user_data
                booking_info = user_data[user_id]['booking_info']
                phone = booking_info['phone']
                selected_service = booking_info['selected_service']
                existing_entry = booking_info['existing_entry']
    
                # Call functions to cancel the booking
                cancel_booking(user_id, phone, selected_service, existing_entry)
    
                # Reset the user's state
                del user_data[user_id]['state']
                del user_data[user_id]['booking_info']
            else:
                bot.sendMessage(user_id, "Invalid command. Please use /cancel     only after checking an existing booking.")



        elif user_id in user_data and 'state' in user_data[user_id]:
            if user_data[user_id]['state'] == 'get_name':
                handle_name_input(user_id, text)
            elif user_data[user_id]['state'] == 'get_phone':
                handle_phone_input(user_id, text)

            elif user_data[user_id]['state'] == 'select_service':
                handle_service_selection(user_id, text)

            elif user_data[user_id]['state'] == 'book_slot':
                handle_slot_entry(user_id, user_data[user_id]['selected_service'], text)
            elif user_data[user_id]['state'] == 'get_phone_exist':
                handle_phone_input_exist(user_id, text)
            elif user_data[user_id]['state'] == 'get_service_exist':
                handle_service_selection_exist(user_id, text)
            
            elif user_data[user_id]['state'] == 'cancel_booking':
                # Check if the user wants to cancel the booking
                if text == '/cancel':
                    # Extract additional information from user_data
                    phone = user_data[user_id].get('phone')
                    selected_service = user_data[user_id].get('selected_service')
                    existing_entry = user_data[user_id].get('existing_entry')

                    # Call the function to cancel the booking
                    cancel_booking(user_id, phone, selected_service, existing_entry)
                else:
                    bot.sendMessage(user_id, 'Invalid command. Please use /cancel only after checking an existing booking.')

    elif content_type == 'callback_query':
        handle_inline_keyboard_callback(msg)


def cancel_booking(user_id, phone, selected_service, existing_entry):
    # Load credentials from the token.json file or create them if it doesn't exist.
    creds = None
    if os.path.exists('google_sheets_token.json'):
        creds = Credentials.from_authorized_user_file('google_sheets_token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/calendar']
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_sheets_token.json', 'w') as token:
            token.write(creds.to_json())

    # Create services using the credentials
    sheets_service = build('sheets', 'v4', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)

    # Spreadsheet ID for your Google Sheets document
    spreadsheet_id = '1P_w0DsEUJ-eIG3REhD2B7K1v5rM_XtjY0coR8cmcAyE'

    # Determine which sheet to read from based on the selected service
    sheet_name = 'Sheet1' if selected_service == "Hair Salon and Beauty Parlour" else 'Sheet2'

    # Construct the range to read from (modify this based on your sheet structure)
    range_to_read = f"{sheet_name}!B:E"

    # Read values from the sheet
    request = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_to_read,
    )
    response = request.execute()
    values = response.get('values', [])

    # Check if there is an entry with the provided phone number and selected service
    existing_entry_index = None
    booking_details = None
    if values:
        for i, row in enumerate(values):
            if row[0] == phone and row[1] == existing_entry[1] and row[2] == existing_entry[2]:
                existing_entry_index = i
                booking_details = row
                break

    # If the entry is found, proceed to delete the event from Google Calendar and the entry from Google Sheets
    if existing_entry_index is not None and booking_details:
        booking_date = booking_details[3]  
        booking_time = booking_details[4]  
        service_name = selected_service

        # Construct the time range for the event search
        start_time = datetime.strptime(f"{booking_date} {booking_time}", "%d-%m-%Y %H:%M")
        end_time = start_time + timedelta(minutes=120) 

        # Convert to RFC3339 timestamp format
        start_time_rfc3339 = start_time.isoformat() + 'Z'
        end_time_rfc3339 = end_time.isoformat() + 'Z'

        # Search for the event on Google Calendar
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=start_time_rfc3339,
            timeMax=end_time_rfc3339,
            q=service_name,  # Search by service name
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if events:
            for event in events:
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                event_end = event['end'].get('dateTime', event['end'].get('date'))
                if event_start == start_time_rfc3339 and event_end == end_time_rfc3339:
                    # Delete the event
                    calendar_service.events().delete(calendarId='primary', eventId=event['id']).execute()
                    break

        # Remove the entry from the sheet
        range_to_remove = f"{sheet_name}!A{existing_entry_index + 1}:E{existing_entry_index + 1}"  # Assuming headers are in the first row
        request = sheets_service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_to_remove,
        )
        request.execute()

        bot.sendMessage(user_id, "Booking and calendar event canceled successfully.")
    else:
        bot.sendMessage(user_id, "No matching booking found.")



def handle_menu(chat_id):
    # Display the menu message
    menu_message = (
        "We offer two services:\n"
        "1) Hair Salon and Beauty Parlour\n"
        "2) Spa and Wellbeing.\n"
        "Please enter 1 for Hair Salon and Beauty Parlour\n or 2 for Spa and Wellbeing"
    )
    bot.sendMessage(chat_id, menu_message)

def handle_exist_command(user_id):
    # Set the user's state to 'get_phone_exist'
    user_data[user_id] = {'state': 'get_phone_exist'}
    # Send a message with an input field for the user to enter their phone number
    bot.sendMessage(user_id, 'Please enter your phone number to check for existing bookings:', reply_markup={'force_reply': True})

def handle_phone_input_exist(user_id, phone):
    # Process the user's phone number input
    user_info = user_data.get(user_id, {})
    user_info['phone'] = phone

    # Set the user's state to 'get_service_exist'
    user_data[user_id]['state'] = 'get_service_exist'
    # Display the service selection menu
    handle_menu(user_id)


def handle_service_selection_exist(user_id, selection):
    if selection in ['1', '2']:
        service_options = ["Hair Salon and Beauty Parlour", "Spa and Wellbeing"]
        selected_service = service_options[int(selection) - 1]
        user_data[user_id]['selected_service'] = selected_service

        # Check for existing bookings based on phone number and service
        check_existing_booking(user_id, user_data[user_id]['phone'], selected_service)
    else:
        bot.sendMessage(user_id, 'Invalid selection. Please enter 1 or 2 to choose a service:', reply_markup={'force_reply': True})


def check_existing_booking(user_id, phone, selected_service):
    # Load credentials from the token.json file or create them if it doesn't exist.
    creds = None
    if os.path.exists('google_sheets_token.json'):
        creds = Credentials.from_authorized_user_file('google_sheets_token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                SHEETS_TOKEN, sheet_scope)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_sheets_token.json', 'w') as token:
            token.write(creds.to_json())

    # Create a service using the credentials
    service = build('sheets', 'v4', credentials=creds)

    # Spreadsheet ID for your Google Sheets document
    spreadsheet_id = '1P_w0DsEUJ-eIG3REhD2B7K1v5rM_XtjY0coR8cmcAyE'

    # Determine which sheet to read from based on the selected service
    sheet_name = 'Sheet1' if selected_service == "Hair Salon and Beauty Parlour" else 'Sheet2'

    # Construct the range to read from (modify this based on your sheet structure)
    range_to_read = f"{sheet_name}!B:E"

    # Read values from the sheet
    request = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_to_read,
    )
    response = request.execute()
    values = response.get('values', [])

    # Check if there is an entry with the provided phone number
    existing_entry = None
    if values:
        for row in values:
            if row[0] == phone:
                existing_entry = row
                break
    print(existing_entry)
    # Display the result to the user
    if existing_entry:
        date_time_str = f"{existing_entry[2]} at {existing_entry[3]}"
        bot.sendMessage(user_id, f"Existing booking found for phone number {phone} in {selected_service} on {date_time_str}.\n")
        bot.sendMessage(user_id, "If you want to cancel this booking type /cancel.")
    else:
        bot.sendMessage(user_id, f"No existing booking found for phone number {phone} in {selected_service}.")
    

    # Set the user's state to 'cancel_booking' regardless of whether an existing booking is found
    user_data[user_id]['state'] = 'cancel_booking'
    user_data[user_id]['booking_info'] = {
        'phone': phone,
        'selected_service': selected_service,
        'existing_entry': existing_entry
    }





def handle_inline_keyboard_callback(msg):
    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')

    if query_data == 'get_name':
        bot.answerCallbackQuery(query_id, text='Please enter your name:')
        # Set the user's state to 'get_name'
        user_data[from_id] = {'state': 'get_name'}
        # Send a message with an input field for the user to enter their name
        bot.sendMessage(from_id, 'Please enter your name:', reply_markup={'force_reply': True})

    elif query_data == 'get_phone':
        bot.answerCallbackQuery(query_id, text='Please enter your phone number:')
        # Set the user's state to 'get_phone'
        user_data[from_id] = {'state': 'get_phone'}
        # Send a message with an input field for the user to enter their phone number
        bot.sendMessage(from_id, 'Please enter your phone number:', reply_markup={'force_reply': True})

def handle_name_input(user_id, name):
    # Process the user's name input
    user_info = user_data.get(user_id, {})
    user_info['name'] = name
    bot.sendMessage(user_id, f'Thank you, {name}! Now, please share your phone number.')
    # Set the user's state to 'get_phone'
    user_data[user_id]['state'] = 'get_phone'

def handle_phone_input(user_id, phone):
    # Process the user's phone number input
    user_info = user_data.get(user_id, {})
    user_info['phone'] = phone
    bot.sendMessage(user_id, f'Thank you for providing your phone number: {phone}. Now, please select a service:')
    # Set the user's state to 'select_service'
    user_data[user_id]['state'] = 'select_service'
    # Display the service selection menu
    handle_menu(user_id)


def handle_service_selection(user_id, selection):
    if selection in ['1', '2']:
        service_options = ["Hair Salon and Beauty Parlour", "Spa and Wellbeing"]
        selected_service = service_options[int(selection) - 1]
        user_data[user_id]['selected_service'] = selected_service

        # Generate slots for the selected service
        available_slots = generate_slots(selected_service)

        # Display available slots
        display_available_slots(user_id, selected_service, available_slots)

        # Set the user's state to 'book_slot'
        user_data[user_id]['state'] = 'book_slot'
    else:
        bot.sendMessage(user_id, 'Invalid selection. Please enter 1 or 2 to choose a service:', reply_markup={'force_reply': True})


def handle_slot_entry(user_id, selected_service, slot_number):
    # Check if the entered slot number is valid
    if not slot_number.isdigit():
        bot.sendMessage(user_id, 'Invalid input. Please enter a numeric slot number.')
        return

    slot_number = int(slot_number)

    if slot_number not in range(1, 15):  # Adjust the range based on your actual slots
        bot.sendMessage(user_id, 'Invalid slot number. Please enter a valid slot number.')
        return

    # Get the user's information
    user_info = user_data.get(user_id, {'name': 'Unknown', 'phone': 'Unknown'})

    # Get the selected day and slot information
    current_date = datetime.now()
    selected_day = current_date + timedelta(days=(slot_number - 1) // 2)
    selected_slot = (slot_number - 1) % 2 + 1

    # Get the start and end times for the selected slot
    start_time = selected_day.replace(hour=selected_slot * 2, minute=0, second=0)
    end_time = start_time + slot_duration

    # Add the booked slot to the respective service's booked slots list
    if selected_service == "Hair Salon and Beauty Parlour":
        booked_slots_hair_beauty.append(slot_number)
    elif selected_service == "Spa and Wellbeing":
        booked_slots_spa_wellbeing.append(slot_number)


        # Authenticate Google Calendar
    cred = authenticate_google_calendar()

    if cred:
        # Build the Google Calendar service
        service = build('calendar', 'v3', credentials=cred)
        # Create a Google Calendar event
        create_calendar_event(cred, service, user_id,selected_service, slot_number, start_time, end_time,bot)

    # Reset the user's state
    # Write booking details to Google Sheets
    write_to_google_sheets(user_info, selected_service, slot_number, start_time)

    # Reset the user's state
    del user_data[user_id]

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
TOKEN = TG_TOKEN
bot = telepot.Bot(TOKEN)

# Set up the message loop
MessageLoop(bot, handle_messages).run_as_thread()

# Keep the program running
while True:
    clear_booked_slots()
    # Sleep for 1 day
    sleep_duration = 24 * 60 * 60  # 24 hours in seconds
    time.sleep(sleep_duration)