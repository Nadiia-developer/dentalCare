import openai
import pandas as pd
import requests
import re
from datetime import datetime
from difflib import get_close_matches


openai.api_key = "API_KEY"


def load_dental_services(file_path):
    df = pd.read_csv(file_path)
    df.columns = ["Dental service", "Price in UAH"]
    return df


def load_schedule(file_path):
    df = pd.read_csv(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Time"] = pd.to_datetime(df["Time"], format="%I:%M:%S %p").dt.time
    return df


def find_service_price(df, user_query):
    services = df["Dental service"].tolist()
    matches = get_close_matches(user_query.lower(), [service.lower() for service in services], n=1, cutoff=0.4)
    if matches:
        matched_service = df[df["Dental service"].str.lower() == matches[0]].iloc[0]
        return f"The price for '{matched_service['Dental service']}' is {matched_service['Price in UAH']} UAH."
    else:
        return None


def suggest_services(df, user_query):
    services = df["Dental service"].tolist()
    matches = get_close_matches(user_query.lower(), [service.lower() for service in services], n=3, cutoff=0.2)
    if matches:
        suggestions = "\n".join(
            [f"- {df[df['Dental service'].str.lower() == match].iloc[0]['Dental service']}" for match in matches])
        return f"Sorry, I couldn't find an exact match. Did you mean one of the following?\n{suggestions}"
    else:
        return f"Sorry, I couldn't find the requested service. Here is a list of available services:\n{list_services(df)}"


def list_services(df):
    services = "\n".join([f"- {service}" for service in df["Dental service"]])
    return f"Here is a list of available dental services:\n{services}"


def check_availability(schedule_df, doctor, date, time):
    date_obj = datetime.strptime(date, "%m/%d/%Y").date()
    time_obj = datetime.strptime(time, "%I:%M %p").time()
    available = ((schedule_df["Name of Doctor"] == doctor) &
                 (schedule_df["Date"].dt.date == date_obj) &
                 (schedule_df["Time"] == time_obj)).any()
    return available


def suggest_available_slots(schedule_df, doctor, date):
    date_obj = datetime.strptime(date, "%m/%d/%Y").date()
    available_slots = schedule_df[
        (schedule_df["Name of Doctor"] == doctor) &
        (schedule_df["Date"].dt.date == date_obj)
        ]["Time"].tolist()
    return [slot.strftime("%I:%M %p") for slot in available_slots]


booked_appointments = {}


def is_valid_email(email):
    """Validate email format using a regex."""
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(email_regex, email) is not None


def book_appointment(schedule_df, dental_services, patient_name):
    """Book an appointment by first choosing a service, then selecting a doctor, date, and time."""
    while True:
        email = input("Enter your email: ").strip()
        if is_valid_email(email):
            break
        else:
            print("\n❌ Invalid email format. Please enter a valid email address.")

    while True:
        service_name = input("Enter the dental service you need: ").strip()
        matched_service = find_service_price(dental_services, service_name)

        if matched_service:
            print("\nBot:", matched_service)
            break
        else:
            print("\nBot:", suggest_services(dental_services, service_name))

    doctor = input("Enter doctor's name (Adam or Daniel): ").strip()
    date = input("Enter date (MM/DD/YYYY, e.g., 1/28/2025): ").strip()
    time = input("Enter time (hh:mm AM/PM, e.g., 3:30 PM): ").strip()

    date_obj = datetime.strptime(date, "%m/%d/%Y").date()
    time_obj = datetime.strptime(time, "%I:%M %p").time()

    if doctor not in booked_appointments:
        booked_appointments[doctor] = set()

    if (date_obj, time_obj) in booked_appointments[doctor]:
        print("\n❌ This time slot is already booked. Please choose a different time.")
        return

    if check_availability(schedule_df, doctor, date, time):
        booked_appointments[doctor].add((date_obj, time_obj))
        print(f"\n✅ Appointment booked for {service_name} with {doctor} on {date} at {time}.")

        webhook_url = "WEBHOOK_URL"
        payload = {
            "patient_name": patient_name,
            "email": email,
            "service": service_name,
            "doctor": doctor,
            "date": date,
            "time": time
        }

        try:
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                print("✅ Appointment details successfully sent to the webhook.")
            else:
                print(f"❌ Failed to send data to webhook. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending data to webhook: {e}")

    else:
        available_slots = suggest_available_slots(schedule_df, doctor, date)
        print("\n❌ Selected slot is unavailable.")
        if available_slots:
            print("Available slots:", ", ".join(available_slots))
        else:
            print("No available slots for this doctor on this date.")


def chatbot():
    dental_services = load_dental_services("dental_services.csv")
    schedule_df = load_schedule("dental_care_schedule.csv")
    print("Welcome to the Dental Service Bot! You can:")
    print("1️⃣ Ask about a dental service price")
    print("2️⃣ List available services (type 'list services')")
    print("3️⃣ Book an appointment (type 'book appointment')")
    print("4️⃣ Exit (type 'exit')")

    while True:
        user_query = input("\nYou: ").strip().lower()
        if user_query in ["exit", "quit"]:
            print("Goodbye!")
            break
        elif user_query in ["list services", "show services"]:
            print("\nBot:", list_services(dental_services))
        elif user_query in ["book appointment"]:
            patient_name = input("Enter your name: ").strip()
            book_appointment(schedule_df, dental_services, patient_name)
        else:
            service_response = find_service_price(dental_services, user_query)
            if service_response:
                print("\nBot:", service_response)
            else:
                print("\nBot:", suggest_services(dental_services, user_query))

                gpt_response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant for a dental clinic."},
                        {"role": "user",
                         "content": f"The available dental services are: {', '.join(dental_services['Dental service'])}. The user asked: '{user_query}'"},
                    ]
                )
                print("\nBot:", gpt_response["choices"][0]["message"]["content"])


if __name__ == "__main__":
    chatbot()
