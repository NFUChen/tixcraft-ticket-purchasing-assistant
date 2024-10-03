from py_spring import PySpringApplication
from py_spring_model import provide_py_spring_model
from src.service.ticket_bot.google_login_handler import GoogleLoginCredential
from src.service.ticket_bot.tixcraft_ticket_assistant import Event, TixcraftTicketAssistant
import typer

app = typer.Typer()

@app.command()
def purchase_ticket(
    event_key_word: str = typer.Option(..., help="Keyword for the event."),
    event_datetime: str = typer.Option(..., help="Date and time of the event (YYYY/MM/DD)."),
    seat_key_word: str = typer.Option(..., help="Keyword for the seat."),
    delivery_key_words: str = typer.Option(..., help="Delivery methods (comma-separated)."),
    payment_key_words: str = typer.Option(..., help="Payment methods (comma-separated)."),
    exclude_key_words: str = typer.Option(..., help="Keywords to exclude (comma-separated)."),
    email: str = typer.Option(..., help="Email for Google login."),
    password: str = typer.Option(..., help="Password for Google login."),
    config_file: str = typer.Option("./app-config.json", help="Path to the app configuration file.")
):

    # Create Event and Credential objects
    event = Event(
        event_key_word=event_key_word,
        event_datetime=event_datetime,
        seat_key_word=seat_key_word,
        delivery_key_words=[kw.strip() for kw in delivery_key_words.split(',') if kw != ''],
        payment_key_words=[kw.strip() for kw in payment_key_words.split(',') if kw != ''],
        exclude_key_words=[kw.strip() for kw in exclude_key_words.split(',') if kw != '']
    )
    credential = GoogleLoginCredential(email=email, password=password)

    # Initialize and run the application
    app_instance = PySpringApplication(config_file, [provide_py_spring_model()])
    app_instance.run()

    # Access the ticket assistant and purchase the ticket
    assistant = app_instance.app_context.get_component(TixcraftTicketAssistant)
    if assistant is not None:
        assistant.purchase_ticket(credential, event)

if __name__ == "__main__":
    app()