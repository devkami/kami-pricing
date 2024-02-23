import json
import logging
from os import path
from typing import List, Tuple

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

gsheet = KamiGsheet(api_version='v4', credentials_path=GOOGLE_API_CREDENTIALS)
pricing_logger = logging.getLogger('Pricing Manager')


class PricingManagerError(Exception):
    pass


class PricingManager:
    def __init__(
        self,
        company: str = 'HAIRPRO',
        marketplace: str = 'BELEZA_NA_WEB',
        integrator: str = 'PLUGG_TO',
        products_ulrs_sheet_name: str = 'pricing',
        skus_sellers_sheet_name: str = 'skushairpro',
    ):
        self.company = company
        self.marketplace = marketplace
        self.products_ulrs_sheet_name = products_ulrs_sheet_name
        self.skus_sellers_sheet_name = skus_sellers_sheet_name
        self.integrator = integrator
        self.integrator_api = None

    @classmethod
    def from_json(cls, file_path: str):
        with open(file_path, 'r') as file:
            json_data = json.load(file)

        company = json_data.get('company', 'HAIRPRO')
        marketplace = json_data.get('marketplace', 'BELEZA_NA_WEB')
        integrator = json_data.get('integrator', 'ANYMARKET')
        products_ulrs_sheet_name = json_data.get(
            'products_ulrs_sheet_name', 'pricing'
        )
        skus_sellers_sheet_name = json_data.get(
            'skus_sellers_sheet_name', 'skushairpro'
        )

        if not all(
            [
                company,
                marketplace,
                integrator,
                products_ulrs_sheet_name,
                skus_sellers_sheet_name,
            ]
        ):
            raise PricingManagerError(
                "JSON file must contain 'company', 'marketplace', 'products_urls_sheet_name', 'skus_sellers_sheet_name' and 'integrator' keys."
            )

        return cls(
            company=company,
            marketplace=marketplace,
            integrator=integrator,
            products_ulrs_sheet_name=products_ulrs_sheet_name,
            skus_sellers_sheet_name=skus_sellers_sheet_name,
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

    def _get_products_from_gsheet(
        self, sheet_id: str = ID_HAIRPRO_SHEET
    ) -> Tuple[List[str], pd.DataFrame]:
        try:
            urls = gsheet.convert_range_to_dataframe(
                sheet_id=sheet_id,
                sheet_range=f'{self.products_ulrs_sheet_name}!A1:A',
            )
            urls = list(urls['urls'])
            sku_sellers = gsheet.convert_range_to_dataframe(
                sheet_id=sheet_id,
                sheet_range=f'{self.skus_sellers_sheet_name}!A1:B',
            )
            sku_sellers = sku_sellers.rename(
                columns={0: 'SKU Seller', 1: 'SKU Beleza'}
            )
            return urls, sku_sellers
        except Exception as e:
            pricing_logger.exception(str(e))
            raise

    def get_products_from_company(self) -> Tuple[List[str], pd.DataFrame]:
        if self.company == 'HAIRPRO':
            return self._get_products_from_gsheet(sheet_id=ID_HAIRPRO_SHEET)
        raise ValueError(f'Unsupported company: {self.company}')

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def scraping_and_pricing(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        try:
            products_urls, products_skus = self.get_products_from_company()
            pc = Pricing()
            sc = Scraper(
                marketplace=self.marketplace, products_urls=products_urls
            )
            sellers_list = sc.scrap_products_from_marketplace()
            pricing_df = pc.create_dataframes(
                sellers_list=sellers_list, skus_list=products_skus
            )
            pricing_df = pc.drop_inactives(pricing_df)
            func_ebitda = pc.ebitda_proccess(pricing_df)
            df_ebitda = pc.pricing(func_ebitda)            
            df_final = pc.drop_inactives(df_ebitda)
            columns = ['sku', 'brand', 'category', 'name', 'price', 'seller_name']
            sellers_df = pd.DataFrame(sellers_list, columns=columns)
            return sellers_df, df_final[['sku (*)', 'special_price']]
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
