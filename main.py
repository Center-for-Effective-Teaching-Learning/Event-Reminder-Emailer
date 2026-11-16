import ast
import configparser
from datetime import datetime
from html import escape

import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking


# Load configuration from config.ini
config = configparser.ConfigParser()
config.read("/home/ubuntu/scripts/config.ini")

# Eventbrite configuration
eventbrite_api_key = config["auth"]["eventbrite"]
organization_id = config["auth"]["eventbrite_id"]

# SendGrid configuration
sendgrid_api_key = config["auth"]["sendgrid_api_key"]
sender_email = "cetltech@calstatela.edu"
summary_recipient = "jhenlin2@calstatela.edu"

# Email settings
image_url = "https://fdms.online/images/cetl_banner.png"
zoom_url = "https://calstatela.zoom.us/j/81813600499"


def clean_text(value):
    """Convert byte strings and byte-string representations to normal text."""
    if value is None:
        return ""

    # Handle actual byte values
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()

    value = str(value).strip()

    # Handle text formatted like b'Deborah' or b"Deborah"
    if value.startswith(("b'", 'b"')):
        try:
            decoded_value = ast.literal_eval(value)

            if isinstance(decoded_value, bytes):
                return decoded_value.decode(
                    "utf-8",
                    errors="replace"
                ).strip()
        except (ValueError, SyntaxError):
            pass

    return value


def get_attendee_name(profile):
    """Build a clean attendee name from the Eventbrite profile."""
    first_name = clean_text(profile.get("first_name"))
    last_name = clean_text(profile.get("last_name"))

    attendee_name = f"{first_name} {last_name}".strip()

    # Fall back to the combined name if first and last are unavailable
    if not attendee_name:
        attendee_name = clean_text(profile.get("name"))

    return attendee_name or "Guest"


def get_events(api_key, organization_id):
    """Get events scheduled for today."""
    url = (
        f"https://www.eventbriteapi.com/v3/"
        f"organizations/{organization_id}/events/"
    )

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    today = datetime.now().strftime("%Y-%m-%d")

    params = {
        "start_date.range_start": today,
        "start_date.range_end": today,
        "order_by": "start_asc",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )
    response.raise_for_status()

    return response.json().get("events", [])


def get_attendees(api_key, event_id):
    """Get registered attendees for an event."""
    url = (
        f"https://www.eventbriteapi.com/v3/"
        f"events/{event_id}/attendees/"
    )

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    return response.json().get("attendees", [])


def format_start_time(start_time):
    """Format an Eventbrite local date and time."""
    dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
    return dt.strftime("%A, %B %d, %Y at %I:%M %p")


def send_email_reminder(
    email,
    event_name,
    start_time,
    access_link,
    attendee_name,
    is_online_event
):
    """Send an event reminder email to one attendee."""
    safe_attendee_name = escape(attendee_name)
    safe_event_name = escape(event_name)
    safe_start_time = escape(start_time)
    safe_access_link = escape(access_link, quote=True)

    if access_link:
        event_display = (
            f'<a href="{safe_access_link}">{safe_event_name}</a>'
        )
    else:
        event_display = safe_event_name

    online_event_paragraph = ""

    if is_online_event:
        online_event_paragraph = (
            f'<p>Join the Zoom meeting here: '
            f'<a href="{zoom_url}">{zoom_url}</a></p>'
        )

    html_content = (
        f'<p><img src="{image_url}" alt="CETL" '
        f'style="width:50%;height:auto;"></p>'
        f'<p>Good morning {safe_attendee_name},</p>'
        f'<p>This is a reminder that you are registered for '
        f'<strong>{event_display}</strong> happening today '
        f'(<strong>{safe_start_time}</strong>).</p>'
        f'{online_event_paragraph}'
        f'<p>We look forward to seeing you there!</p>'
        f'<p>Best regards,<br>CETL</p>'
    )

    message = Mail(
        from_email=sender_email,
        to_emails=email,
        subject=f'Reminder: You are registered for "{event_name}" today!',
        html_content=html_content
    )

    # Disable SendGrid click tracking
    tracking_settings = TrackingSettings()
    tracking_settings.click_tracking = ClickTracking(
        enable=False,
        enable_text=False
    )
    message.tracking_settings = tracking_settings

    try:
        sendgrid = SendGridAPIClient(sendgrid_api_key)
        response = sendgrid.send(message)

        now = datetime.now()
        formatted_time = now.strftime("%-m/%-d/%y at %-I:%M%p")

        print(
            f"Email sent to {email} on {formatted_time}! "
            f"Status code: {response.status_code}"
        )
        return True, None

    except Exception as error:
        print(f"Error sending email to {email}: {error}")
        return False, str(error)


def build_summary_html(report):
    """Render the admin digest for one reminder run."""
    events_error = report.get("events_error")

    if events_error:
        safe_error = escape(events_error)
        return (
            f"<p>Unable to retrieve Eventbrite events: "
            f"{safe_error}</p>"
        )

    events = report.get("events", [])

    if not events:
        return "<p>No events were scheduled for today.</p>"

    date = escape(report["date"])
    sections = [f"<p>Event reminder summary for {date}.</p>"]
    sent = 0
    failed = 0
    skipped = 0

    for event in events:
        safe_name = escape(event["name"])
        safe_start = escape(event["start_time"])
        location = "Online" if event["online"] else "In person"

        sections.append(f"<h2>{safe_name}</h2>")
        sections.append(f"<p>{safe_start}<br>{location}</p>")

        fetch_error = event.get("fetch_error")

        if fetch_error:
            sections.append(
                f"<p>Unable to retrieve attendees: "
                f"{escape(fetch_error)}</p>"
            )
            continue

        attendees = event.get("attendees", [])

        if not attendees:
            sections.append("<p>No registered users.</p>")
            continue

        items = []

        for attendee in attendees:
            name = escape(attendee["name"])
            email = attendee.get("email") or ""
            status = attendee["status"]

            if status == "sent":
                sent += 1
                result = "Sent"
            elif status == "failed":
                failed += 1
                error = attendee.get("error") or "Unknown error"
                result = f"Failed: {escape(error)}"
            else:
                skipped += 1
                result = "Missing email"

            if email:
                contact = f"{name} ({escape(email)})"
            else:
                contact = name

            items.append(f"<li>{contact} - {result}</li>")

        sections.append("<ul>" + "".join(items) + "</ul>")

    sections.append(
        f"<p><strong>Totals:</strong> {sent} sent, "
        f"{failed} failed, {skipped} skipped.</p>"
    )

    return "".join(sections)


def send_summary_email(report):
    """Send one digest of today's reminder run."""
    html_content = build_summary_html(report)

    message = Mail(
        from_email=sender_email,
        to_emails=summary_recipient,
        subject=f"Event reminder summary for {report['date']}",
        html_content=html_content
    )

    tracking_settings = TrackingSettings()
    tracking_settings.click_tracking = ClickTracking(
        enable=False,
        enable_text=False
    )
    message.tracking_settings = tracking_settings

    try:
        sendgrid = SendGridAPIClient(sendgrid_api_key)
        response = sendgrid.send(message)

        now = datetime.now()
        formatted_time = now.strftime("%-m/%-d/%y at %-I:%M%p")

        print(
            f"Summary email sent to {summary_recipient} "
            f"on {formatted_time}! "
            f"Status code: {response.status_code}"
        )

    except Exception as error:
        print(
            f"Error sending summary email to "
            f"{summary_recipient}: {error}"
        )


def main():
    summary_date = datetime.now().strftime("%B %-d, %Y")
    report = {
        "date": summary_date,
        "events_error": None,
        "events": [],
    }

    try:
        events = get_events(eventbrite_api_key, organization_id)
    except requests.RequestException as error:
        print(f"Unable to retrieve Eventbrite events: {error}")
        report["events_error"] = str(error)
        send_summary_email(report)
        return

    if not events:
        today = datetime.today().strftime("%B %d, %Y")
        print(f"No events found for {today}.")
        send_summary_email(report)
        return

    print("Events happening today:")

    all_emails = []

    for event in events:
        event_id = event["id"]
        event_name = clean_text(event["name"]["text"])
        start_time = event["start"]["local"]
        formatted_start_time = format_start_time(start_time)
        is_online_event = event.get("online_event", False)
        access_link = event.get("url", "") if is_online_event else ""

        event_report = {
            "name": event_name,
            "start_time": formatted_start_time,
            "online": is_online_event,
            "fetch_error": None,
            "attendees": [],
        }

        print(f"\nEvent Name: {event_name}")
        print(f"Start Date: {formatted_start_time}")

        try:
            attendees = get_attendees(
                eventbrite_api_key,
                event_id
            )
        except requests.RequestException as error:
            print(
                f"Unable to retrieve attendees for "
                f"{event_name}: {error}"
            )
            event_report["fetch_error"] = str(error)
            report["events"].append(event_report)
            continue

        if not attendees:
            print("No registered users.")
            report["events"].append(event_report)
            continue

        print("Registered Users:")

        for attendee in attendees:
            profile = attendee.get("profile", {})

            email = clean_text(profile.get("email"))
            attendee_name = get_attendee_name(profile)

            print(f"- {attendee_name} ({email or 'No Email'})")

            if not email:
                print(
                    f"Failed to send email: Missing email "
                    f"for attendee {attendee_name}"
                )
                event_report["attendees"].append({
                    "name": attendee_name,
                    "email": "",
                    "status": "missing_email",
                    "error": None,
                })
                continue

            all_emails.append(email)

            ok, error = send_email_reminder(
                email=email,
                event_name=event_name,
                start_time=formatted_start_time,
                access_link=access_link,
                attendee_name=attendee_name,
                is_online_event=is_online_event
            )
            event_report["attendees"].append({
                "name": attendee_name,
                "email": email,
                "status": "sent" if ok else "failed",
                "error": None if ok else error,
            })

        report["events"].append(event_report)

    print(f"\nTotal count of emails: {len(all_emails)}")
    send_summary_email(report)


if __name__ == "__main__":
    main()
