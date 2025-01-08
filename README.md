# Event Reminder Emailer

A Python script to fetch Eventbrite events for the day, retrieve registered attendees, and send email reminders using SendGrid.

## Features

- Fetches events for the current day from Eventbrite.
- Retrieves attendees for each event.
- Sends personalized email reminders to attendees using SendGrid.

## Prerequisites

- Python 3.7 or later
- `requests` library
- `sendgrid` library
- An `Eventbrite` API key and organization ID
- A `SendGrid` API key
- Configuration file (`config.ini`) with the required authentication details.
