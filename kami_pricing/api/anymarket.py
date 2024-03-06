import json
import logging
from os import path
from typing import Dict, List

import httpx
import pandas as pd
from kami_logging import benchmark_with, logging_with

from kami_pricing.constant import ROOT_DIR

anymarket_api_logger = logging.getLogger('Anymarket API')
test_base_url = 'https://sandbox-api.anymarket.com.br'
base_url = 'https://api.anymarket.com.br'
anymarket_credentials_path = path.join(
    ROOT_DIR, 'credentials/anymarket_hairpro.json'
)


class AnymarketAPIError(Exception):
    pass


class AnymarketAPI:
    def __init__(
        self,
        base_url: str = base_url,
        credentials_path: str = anymarket_credentials_path,
    ):
        self.base_url = base_url
        self.credentials_path = credentials_path
        self.credentials = None
        self.result = None

    def _set_credentials(self):
        try:
            with open(self.credentials_path, 'r') as f:
                self.credentials = json.load(f)
        except FileNotFoundError:
            raise AnymarketAPIError(
                f'Credentials file not found at {self.credentials_path}.'
            )
        except PermissionError:
            raise AnymarketAPIError(
                f'No permission to read credentials file at {self.credentials_path}.'
            )
        except json.JSONDecodeError:
            raise AnymarketAPIError(
                f'The credentials file at {self.credentials_path} contains invalid JSON.'
            )
        except Exception as e:
            raise AnymarketAPIError(f'Failed to get credentials: {str(e)}')

    def _connect(
        self,
        method: str = 'GET',
        endpoint: str = '',
        payload: List = [],
        headers: Dict = {},
    ):
        try:
            if not self.credentials:
                self._set_credentials()

            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
            headers['gumgaToken'] = self.credentials['token']

            method = method.upper()

            with httpx.Client() as client:
                response = {
                    'GET': lambda: client.get(
                        self.base_url + endpoint, headers=headers
                    ),
                    'POST': lambda: client.post(
                        self.base_url + endpoint, json=payload, headers=headers
                    ),
                    'PUT': lambda: client.put(
                        self.base_url + endpoint, json=payload, headers=headers
                    ),
                    'DELETE': lambda: client.delete(
                        self.base_url + endpoint, headers=headers
                    ),
                    'PATCH': lambda: client.patch(
                        self.base_url + endpoint, json=payload, headers=headers
                    ),
                }.get(method, lambda: None)()

                if response is None:
                    raise ValueError(f'Unsupported HTTP method: {method}')

                response.raise_for_status()
                self.result = response.json()

        except httpx.HTTPStatusError as e:
            raise AnymarketAPIError(f'HTTP error occurred: {str(e)}')
        except httpx.RequestError as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')
        except ValueError as e:
            raise AnymarketAPIError(str(e))
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    def get_products_quantity(self) -> int:
        try:
            self._connect(endpoint='/v2/products')
            total_elements = self.result['page']['totalElements']
            return total_elements
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    def get_product_by_id(self, product_id: str) -> Dict:
        try:
            self._connect(endpoint=f'/v2/products/{product_id}')
            anymarket_api_logger.info(
                f"Product: {self.result['id']} successfully retrieved"
            )
            return self.result
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_products_by_ids(self, product_ids: List[str]) -> List[Dict]:
        try:
            result = []
            for product_id in product_ids:
                result.append(self.get_product_by_id(product_id))
            self.result = result
            return self.result
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_ads_by_partner_id(self, partner_id: str) -> List[Dict]:
        try:
            self._connect(
                endpoint=f'/v2/skus/marketplaces?partnerID={partner_id}'
            )
            return self.result
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    def get_product_by_partner_id(self, partner_id: str) -> Dict:
        try:
            self._connect(endpoint=f'/v2/products?partnerId={partner_id}')
            return self.result.get('content', [])[0]
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_products_by_partner_ids(
        self, partner_ids: List[str]
    ) -> List[Dict]:
        try:
            result = []
            for partner_id in partner_ids:
                result.append(self.get_product_by_partner_id(partner_id))
            self.result = result
            return self.result
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    def get_first_ad_of_marketplace(
        self, ads: List[Dict], marketplace: str
    ) -> Dict:
        return next(
            (ad for ad in ads if ad['marketPlace'] == marketplace), None
        )

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_all_products(self) -> List[Dict]:
        try:
            quantity = self.get_products_quantity()
            self._connect(endpoint=f'/v2/products?limit={quantity}')
            return self.result.get('content', [])
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_all_products_ids(self) -> List[str]:
        try:
            products = self.get_all_products()
            product_ids = [product['id'] for product in products]
            return product_ids
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_all_products_partner_ids(self) -> List[str]:
        try:
            products = self.get_all_products()
            partner_ids = [
                sku.get('partnerId', '')
                for product in products
                for sku in product.get('skus', [])
            ]
            return partner_ids
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_partner_and_product_ids(self) -> (List[str], List[str]):
        try:
            products = self.get_all_products()
            partner_ids = [
                sku.get('partnerId', '')
                for product in products
                for sku in product.get('skus', [])
            ]
            product_ids = [product['id'] for product in products]
            return partner_ids, product_ids
        except Exception as e:
            raise AnymarketAPIError(f'Failed to connect: {str(e)}')

    def set_product_for_manual_pricing(self, product_id: str):
        try:
            payload = {
                'calculatedPrice': False,
                'definitionPriceScope': 'SKU_MARKETPLACE',
            }
            headers = {'Content-Type': 'application/merge-patch+json'}
            self._connect(
                method='PATCH',
                endpoint=f'/v2/products/{product_id}',
                headers=headers,
                payload=payload,
            )
            anymarket_api_logger.info(
                f'Set product: {product_id} for manual pricing'
            )
        except Exception as e:
            anymarket_api_logger.exception(str(e))

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def set_products_for_manual_pricing(self, product_ids: list):
        try:
            for product_id in product_ids:
                self.set_product_for_manual_pricing(product_id)
        except Exception as e:
            anymarket_api_logger.exception(str(e))

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def get_products_ads(self, partner_ids: list):
        try:
            advertisements = []
            for partner_id in partner_ids:
                advertisements.extend(
                    self.get_ads_by_partner_id(partner_id=partner_id)
                )
            ads_df = pd.json_normalize(advertisements)
            ads_df.rename(
                columns={'skuInMarketplace': 'sku (*)'}, inplace=True
            )
            ads_df = ads_df[
                [
                    'sku (*)',
                    'id',
                    'marketPlace',
                    'publicationStatus',
                    'marketplaceStatus',
                    'price',
                    'fields.title',
                ]
            ]
            ads_df.dropna(subset=['fields.title'], inplace=True)
            return ads_df
        except Exception as e:
            anymarket_api_logger.exception(str(e))

    def update_price(self, ad_id: str, new_price: float):
        payload = {
            'id': ad_id,
            'price': new_price,
            'discountPrice': new_price,
        }
        self._connect(
            method='PUT',
            endpoint='/v2/skus/marketplaces/prices',
            payload=[payload],
        )
        anymarket_api_logger.info(
            f'Advertisement: {ad_id} updated price to {new_price}'
        )

    def change_price(self, marketplace: str, ads_df: pd.DataFrame):
        try:
            for index, row in ads_df[
                ads_df['marketPlace'] == marketplace
            ].iterrows():
                self.update_price(row['id'], row['special_price'])
        except Exception as e:
            anymarket_api_logger.exception(str(e))

    def get_from_marketplace(self, marketplace: str):
        self._connect(
            endpoint='/v2/transmissions/marketplace/0/0/sort/statusFilter'
        )
        return self.result

    @benchmark_with(anymarket_api_logger)
    @logging_with(anymarket_api_logger)
    def update_prices_on_all_marketplaces(self, pricing_df: pd.DataFrame):
        try:

            self._set_integrator_api()
            for index, row in pricing_df.iterrows():
                product = self.get_product_by_partner_id(
                    partner_id=row['sku (*)']
                )
                self.set_product_for_manual_pricing(product_id=product['id'])
                ads = self.get_ads_by_partner_id(partner_id=row['sku (*)'])
                for ad in ads:
                    self.update_price(
                        ad_id=ad['id'], new_price=row['special_price']
                    )
        except Exception as e:
            anymarket_api_logger.exception(str(e))
            raise

    def update_prices_on_marketplace(
        self, pricing_df: pd.DataFrame, marketplace: str = 'BELEZA_NA_WEB'
    ):
        for index, row in pricing_df.iterrows():
            try:
                product = self.get_product_by_partner_id(
                    partner_id=row['sku (*)']
                )
                self.set_product_for_manual_pricing(product_id=product['id'])
                ads = self.get_ads_by_partner_id(partner_id=row['sku (*)'])
                marketplace_ad = self.get_first_ad_of_marketplace(
                    ads=ads, marketplace=marketplace
                )
                formatted_price = f"{row['special_price']:.2f}"
                self.update_price(
                    ad_id=marketplace_ad['id'], new_price=formatted_price
                )
            except Exception as e:
                anymarket_api_logger.exception(str(e))
                continue
