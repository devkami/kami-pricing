import json
import logging
from dataclasses import dataclass, field
from os import path
from typing import List, Tuple, Union

import pandas as pd
from kami_gsuite.kami_gsheet import KamiGsheet
from kami_logging import benchmark_with, logging_with

from kami_pricing.api.anymarket import AnymarketAPI
from kami_pricing.api.plugg_to import PluggToAPI
from kami_pricing.constant import (
    GOOGLE_API_CREDENTIALS,
    ID_HAIRPRO_SHEET,
    ROOT_DIR,
)
from kami_pricing.pricing import Pricing
from kami_pricing.scraper import Scraper

pricing_logger = logging.getLogger('Pricing Manager')


class PricingManagerError(Exception):
    pass


@dataclass
class PricingManager:
    company: str = ('HAIRPRO',)
    marketplace: str = ('BELEZA_NA_WEB',)
    integrator: str = ('ANYMARKET',)
    integrator_api = None
    gsheet: KamiGsheet = field(init=False)
    gsheet_id: str = (ID_HAIRPRO_SHEET,)
    gsheet_name: str = ('pricing',)
    pricing_engine: Pricing = field(default_factory=Pricing)

    def __post_init__(self):
        self.gsheet = KamiGsheet(
            credentials_path=GOOGLE_API_CREDENTIALS, api_version='v4'
        )
        self._set_integrator_api()
        self.pricing = Pricing(**self.pricing_engine)

    @classmethod
    def from_json(cls, json_data: Union[str, dict]):
        if isinstance(json_data, str) and path.isfile(json_data):
            try:
                json_data = cls._load_json_from_file(json_data)
            except PricingManagerError as e:
                raise e
        elif isinstance(json_data, str):
            try:
                json_data = cls._load_json_from_string(json_data)
            except PricingManagerError as e:
                raise e
        elif isinstance(json_data, dict):
            pass
        else:
            raise PricingManagerError('Invalid JSON data format.')

        cls._validate_json_data(json_data)

        return cls(**json_data)

    @classmethod
    def _load_json_from_string(cls, json_string: str):
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            raise PricingManagerError('Invalid JSON string.')

    @classmethod
    def _load_json_from_file(cls, file_path: str):
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            raise PricingManagerError('Invalid JSON file.')

    @classmethod
    def _validate_json_data(cls, json_data: dict):
        required_keys = [
            'company',
            'marketplace',
            'integrator',
            'gsheet_id',
            'gsheet_name',
        ]
        missing_keys = [key for key in required_keys if key not in json_data]

        if missing_keys:
            raise PricingManagerError(
                f"Missing required keys in JSON data: {', '.join(missing_keys)}"
            )

    def _set_integrator_api(self):
        try:
            if (
                self.integrator.upper() == 'PLUGG_TO'
                and self.marketplace.upper() != 'BELEZA_NA_WEB'
            ):
                raise PricingManagerError(
                    f'PluggTo only support BELEZA NA WEB marktplace.'
                )

            if self.integrator.upper() == 'ANYMARKET':
                self.integrator_api = AnymarketAPI(
                    credentials_path=path.join(
                        ROOT_DIR,
                        f'credentials/anymarket_{self.company.lower()}.json',
                    )
                )
            elif self.integrator.upper() == 'PLUGG_TO':
                self.integrator_api = PluggToAPI(
                    credentials_path=path.join(
                        ROOT_DIR,
                        f'credentials/plugg_to_{self.company.lower()}.json',
                    )
                )
            else:
                raise PricingManagerError(
                    f'Unsupported integrator: {self.integrator}'
                )

        except Exception as e:
            pricing_logger.exception(str(e))
            raise

    def _get_products_from_gsheet(self) -> pd.DataFrame:
        try:
            products_df = self.gsheet.convert_range_to_dataframe(
                sheet_id=self.gsheet_id,
                sheet_range=f'{self.gsheet_name}!A1:D',
            )
            return products_df
        except Exception as e:
            pricing_logger.exception(str(e))
            raise

    def get_products_from_company(self) -> pd.DataFrame:
        if self.company == 'HAIRPRO':
            return self._get_products_from_gsheet()
        raise ValueError(f'Unsupported company: {self.company}')

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def scraping_and_pricing(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        try:
            products_df = self.get_products_from_company()
            products_df = products_df[products_df['status'] == 'ATIVO']
            sc = Scraper(
                marketplace=self.marketplace,
                products_urls=products_df['urls'].tolist(),
            )
            sellers_list = sc.scrap_products_from_marketplace()
            pricing_df = self.pricing.create_dataframes(
                sellers_list=sellers_list, products_df=products_df
            )
            func_ebitda = self.pricing.ebitda_proccess(pricing_df)
            pricing_df = self.pricing.pricing(func_ebitda)
            columns = [
                'sku',
                'brand',
                'category',
                'name',
                'price',
                'seller_name',
            ]
            sellers_df = pd.DataFrame(sellers_list, columns=columns)
            return sellers_df, pricing_df[['sku (*)', 'special_price']]
        except Exception as e:
            pricing_logger.exception(str(e))
            raise

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def update_prices(self, pricing_df: pd.DataFrame):
        try:
            if not self.integrator_api:
                self._set_integrator_api()

            if self.integrator == 'PLUGG_TO':
                self.integrator_api.update_prices(pricing_df=pricing_df)

            elif self.integrator == 'ANYMARKET':
                self.integrator_api.update_prices_on_marketplace(
                    pricing_df=pricing_df, marketplace=self.marketplace
                )

            else:
                raise PricingManagerError(
                    f'Unsupported integrator: {self.integrator}'
                )

        except Exception as e:
            pricing_logger.exception(str(e))
            raise
