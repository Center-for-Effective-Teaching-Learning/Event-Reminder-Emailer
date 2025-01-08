import requests
import configparser
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking
from datetime import datetime

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('/home/bitnami/scripts/config.ini')

# Eventbrite configuration
eventbrite_api_key = config['auth']['eventbrite']
organization_id = config['auth']['eventbrite_id']

# SendGrid configuration
sendgrid_api_key = config['auth']['sendgrid_api_key']
sender_email = "cetltech@calstatela.edu"

# Email settings
image_url = "https://fdms.online/images/cetl_banner.png"


# Function to get events for the day
def get_events(api_key, organization_id):
    url = f"https://www.eventbriteapi.com/v3/organizations/{organization_id}/events/"
    headers = {"Authorization": f"Bearer {api_key}"}
    now = datetime.now()
    start_date = now.strftime('%Y-%m-%d')
    params = {
        "start_date.range_start": start_date,
        "start_date.range_end": start_date,
        "order_by": "start_asc",
    }
    response = requests.get(url, headers=headers, params=params)
    events = response.json().get('events', [])
    return events


# Function to get attendees for an event
def get_attendees(api_key, event_id):
    url = f"https://www.eventbriteapi.com/v3/events/{event_id}/attendees/"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    return response.json().get('attendees', [])


# Function to send email reminder
def send_email_reminder(email, event_name, start_time, access_link, attendee_name):
    message = Mail(
        from_email=sender_email,
        to_emails=email,
        subject=f'Reminder: You are registered for "{event_name}" today!',
        html_content=(
            f'<p><img src="{image_url}" alt="Event Banner" style="width:50%;height:auto;"></p>'
            f'<p>Good morning {attendee_name},</p>'
            f'<p>This is a reminder that you are registered for <strong><a href=\"{access_link}\">{event_name}</a></strong> '
            f'happening today (<strong>{start_time}</strong>).</p>'
            f'</p><p>If this is an online event, join the zoom here: https://calstatela.zoom.us/s/81813600499</p>'
            f'</p><p>We look forward to seeing you there!</p>'
            f'<p>Best regards,</p>'
            f'<p>CETL</p>'
        )
    )

    # Disable click tracking
    tracking_settings = TrackingSettings()
    tracking_settings.click_tracking = ClickTracking(enable=False, enable_text=False)
    message.tracking_settings = tracking_settings

    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        print(f"Email sent to {email}! Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending email to {email}: {e}")


# Function to format the start time
def format_start_time(start_time):
    dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S')
    return dt.strftime('%A, %B %d, %Y at %I:%M %p')


# Main function
def main():
    events = get_events(eventbrite_api_key, organization_id)
    if not events:
        print("No events found for today.")
        return

    print("Events happening today:")
    all_emails = []
    for event in events:
        event_id = event['id']
        event_name = event['name']['text']
        start_time = event['start']['local']
        formatted_start_time = format_start_time(start_time)
        access_link = event.get('url', '') if event.get('online_event') else ''

        print(f"Event Name: {event_name}")
        print(f"Start Date: {start_time}")

        attendees = get_attendees(eventbrite_api_key, event_id)
        if not attendees:
            print("No registered users.")
            continue

        print("Registered Users:")
        for attendee in attendees:
            print(f"- {attendee['profile'].get('name', 'Unknown')} ({attendee['profile'].get('email', 'No Email')})")
            email = attendee['profile'].get('email')
            attendee_name = attendee['profile'].get('name', 'Unknown')
            if email:
                all_emails.append(email)
                send_email_reminder(email, event_name, formatted_start_time, access_link, attendee_name)
            else:
                print(f"Failed to send email: Missing 'email' for attendee {attendee_name}")

    print(f"\nTotal count of emails: {len(all_emails)}")


if __name__ == "__main__":
    main()