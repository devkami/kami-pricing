import json
import time
from os import listdir, path, remove

import schedule

from kami_pricing.constant import PRICING_MANAGER_FILE, ROOT_DIR
from kami_pricing.messages import get_contacts_from_json, send_email_by_group
from kami_pricing.pricing_manager import PricingManager, pricing_logger

contacts = get_contacts_from_json(
    path.join(ROOT_DIR, 'messages/contacts.json')
)
reports_folder = path.join(ROOT_DIR, 'reports')


def _get_files_from(folder_path):
    files = []
    for file in listdir(folder_path):
        full_path = path.join(folder_path, file)
        if path.isfile(full_path):
            files.append(full_path)
    return files


def _remove_files_from(folder_path):
    for filename in _get_files_from(folder_path):
        file_path = path.join(folder_path, filename)
        try:
            remove(file_path)

        except Exception as e:
            pricing_logger.error(f'Failed to delete {file_path}. Reason: {str(e)}')


def update_prices():
    pricing_logger.info('Updating prices...')
    pricing_manager = PricingManager.from_json(file_path=PRICING_MANAGER_FILE)
    scraping_df, pricing_df = pricing_manager.scraping_and_pricing()
    pricing_df = pricing_df.sort_values(by='sku (*)', ascending=False)
    _remove_files_from(reports_folder)
    pricing_df.to_excel(
        reports_folder + '/novos_precos.xlsx', index=False, engine='openpyxl'
    )
    scraping_df.to_excel(
        reports_folder + '/concorrentes.xlsx', index=False, engine='openpyxl'
    )
    pricing_df = pricing_df[['sku (*)', 'special_price']]
    pricing_manager.update_prices(pricing_df=pricing_df)


def send_emails():
    pricing_logger.info('Sending emails...')
    reports = _get_files_from(reports_folder)
    send_email_by_group(
        template_name='pricing',
        group='pricing',
        message_dict={'subject': 'Precificação de produtos'},
        contacts=contacts,
        attachments=reports,
    )
    _remove_files_from(reports_folder)


def main():    
    update_prices()
    send_emails()

    with open(PRICING_MANAGER_FILE, 'r') as file:
        json_data = json.load(file)
        secs = json_data.get('every_seconds')

    schedule.every(secs).seconds.do(update_prices)
    schedule.every(secs*1.2).seconds.do(send_emails)

    while True:
        try:
            schedule.run_pending()
            time.sleep(5)
        except Exception as e:
            pricing_logger.info(f'Error when updating prices: {str(e)}')


if __name__ == '__main__':
    main()
