from os import path
from typing import List, Tuple

import pandas as pd
from kami_gsuite.kami_gsheet import KamiGsheet

from kami_pricing.api.anymarket import AnymarketAPI
from kami_pricing.api.plugg_to import PluggToAPI
from kami_pricing.constant import (
    GOOGLE_API_CREDENTIALS,
    ID_HAIRPRO_SHEET,
    ROOT_DIR,
)
from kami_pricing.pricing import Pricing, pricing_logger
from kami_pricing.scraper import Scraper

gsheet = KamiGsheet(api_version='v4', credentials_path=GOOGLE_API_CREDENTIALS)

class PricingManagerError(Exception):
    pass

class PricingManager:
    def __init__(self, company: str, marketplace: str, integrator: str):
        self.company = company
        self.marketplace = marketplace
        self.integrator = integrator
        self.integrator_api = None

    def _set_integrator_api(self):
        try:
            if self.integrator.upper() == 'PLUGG_TO'\
            and self.marketplace.upper() != 'BELEZA_NA_WEB':
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
            pricing_logger.exception(e)
            raise

    def _get_products_from_gsheet(
        self, sheet_id: str = ID_HAIRPRO_SHEET, urls_sheet: str ='pricing_teste', sellers_sheet: str = 'skushairpro'
    ) -> Tuple[List[str], pd.DataFrame]:
        try:
            urls = gsheet.convert_range_to_dataframe(
                sheet_id=sheet_id,
                sheet_range=f'{urls_sheet}!A1:A',
            )
            urls = list(urls['urls'])
            sku_sellers = gsheet.convert_range_to_dataframe(
                sheet_id=sheet_id,
                sheet_range=f'{sellers_sheet}!A1:B',
            )
            sku_sellers = sku_sellers.rename(
                columns={0: 'SKU Seller', 1: 'SKU Beleza'}
            )
            return urls, sku_sellers
        except Exception as e:
            pricing_logger.exception(e)
            raise

    def get_products_from_company(self) -> Tuple[List[str], pd.DataFrame]:
        if self.company == 'HAIRPRO':
            return self._get_products_from_gsheet(sheet_id=ID_HAIRPRO_SHEET)
        raise ValueError(f'Unsupported company: {self.company}')

    def scraping_and_pricing(self) -> pd.DataFrame:
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
            return df_final[['sku (*)', 'special_price']]
        except Exception as e:
            pricing_logger.exception(e)
            raise

    def update_prices(self, pricing_df: pd.DataFrame):
        try:
            if not self.integrator_api:
                self._set_integrator_api()

            if self.integrator == 'PLUGG_TO':
                self.integrator_api.update_prices(pricing_df=pricing_df)
            
            elif self.integrator == 'ANYMARKET':
                self.integrator_api.update_prices_on_marketplace(
                    pricing_df=pricing_df,
                    marketplace=self.marketplace
                )
            
            else:
                raise PricingManagerError(
                    f'Unsupported integrator: {self.integrator}'
                )
            
        except Exception as e:
            pricing_logger.exception(e)
            raise