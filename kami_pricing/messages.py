import json
import logging
from dataclasses import dataclass, field
from os import getenv, path
from typing import Dict, List

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from kami_logging import benchmark_with, logging_with
from kami_messenger.botconversa import Botconversa
from kami_messenger.email_messenger import EmailMessenger
from kami_messenger.messenger import Message

from kami_pricing.constant import ROOT_DIR

load_dotenv()
messages_looger = logging.getLogger('Messages Generator')
template_loader = FileSystemLoader(path.join(ROOT_DIR, 'messages/templates'))
template_env = Environment(loader=template_loader)
MESSENGER_TYPES = ['whatsapp', 'email']


@dataclass(order=True)
class Contact:
    sort_index: int = field(init=False, repr=False)
    id: int = 0
    name: str = ''
    email: str = ''
    phone: str = ''
    groups: list = field(default_factory=list)

    def __post_init__(self):
        self.sort_index = self.id


def get_contacts_from_json(json_file) -> List[Contact]:
    contacts = []
    with open(json_file) as contacts_file:
        contacts_dict = json.load(contacts_file)

    for contact_dict in contacts_dict:
        contact = Contact(**contact_dict)
        contacts.append(contact)

    return contacts


def get_contact_by_id(
    search_id: int, contacts: List[Contact]
) -> Contact | None:
    for contact in contacts:
        if contact.id == search_id:
            return contact
    messages_looger.error(
        f'There is no contact for the given id! given id = {search_id}'
    )
    return None


def filter_contact_by_group(
    contacts: List[Contact], group: str
) -> List[Contact]:
    return [contact for contact in contacts if group in contact.groups]


def generate_message_by_template(
    template_name: str, contact: Contact, message_dict: Dict
) -> Message | None:
    message_template = template_env.get_template(f'{template_name}_message.md')
    message_dict['contact_name'] = contact.name
    message_body = message_template.render(message_dict)
    return Message(
        sender='',
        recipients=[],
        body=message_body,
        subject=message_dict['subject'],
    )


def send_email(message: Message, attachments: List[str] = []):
    login = str(getenv('EMAIL_USER'))
    password = str(getenv('EMAIL_PASSWORD'))
    message.sender = login
    email_messenger_str = {
        'name': 'Email - kamico.com.br',
        'messages': [message],
        'credentials': {
            'login': login,
            'password': password,
        },
        'engine': '',
    }
    email_messenger = EmailMessenger(**email_messenger_str)
    email_messenger.sendMessage(attachments=attachments)


@logging_with(messages_looger)
def send_whatsapp_message(message):
    botconversa_data = {
        'name': 'Botconversa',
        'messages': [message],
        'credentials': {'api-key': str(getenv('BOTCONVERSA_API_KEY'))},
        'engine': '',
    }
    botconversa = Botconversa(**botconversa_data)
    botconversa.sendMessage()


@logging_with(messages_looger)
def send_message_by_messenger(
    messenger: str,
    message: Message,
    contact: Contact,
    attachments: List[str] = [],
):
    if messenger not in MESSENGER_TYPES:
        messages_looger.error(f"Mesenger Type:{messenger}, does not exit's")

    if messenger == 'whatsapp':
        message.recipients = [contact.phone]
        send_whatsapp_message(message=message)

    if messenger == 'email':
        message.recipients = [contact.email]
        send_email(message=message, attachments=attachments)

    messages_looger.error('Unable to send message')


@logging_with(messages_looger)
@benchmark_with(messages_looger)
def send_message_by_all_messengers(
    message: Message, contact: Contact, attachments: List[str] = []
):
    for messenger in MESSENGER_TYPES:
        send_message_by_messenger(messenger, message, contact, attachments)


def send_message_by_group(
    template_name: str,
    group: str,
    message_dict: Dict,
    contacts: List[Contact],
    attachments: List[str] = [],
):
    filtered_contacts = filter_contact_by_group(contacts, group)
    for contact in filtered_contacts:
        message = generate_message_by_template(
            template_name, contact, message_dict
        )
        send_message_by_all_messengers(message, contact, attachments)


def send_email_by_group(
    template_name: str,
    group: str,
    message_dict: Dict,
    contacts: List[Contact],
    attachments: List[str] = [],
):
    filtered_contacts = filter_contact_by_group(contacts, group)
    for contact in filtered_contacts:
        message = generate_message_by_template(
            template_name, contact, message_dict
        )
        message.recipients = [contact.email]
        send_email(message=message, attachments=attachments)
