import json
import logging
from typing import List

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from kami_gsuite.kami_gsheet import KamiGsheet
from kami_logging import benchmark_with, logging_with

from kami_pricing.constant import (
    COLUMNS_ALL_SELLER,
    COLUMNS_DIFERENCE,
    COLUMNS_EXCEPT_HAIRPRO,
)

scraper_logger = logging.getLogger('scraper')


class Scraper:
    def __init__(
        self,
        marketplace: str = 'BELEZA_NA_WEB',
        products_urls: List[str] = None,
    ):
        self.marketplace = marketplace
        self.products_urls = products_urls

    @benchmark_with(scraper_logger)
    @logging_with(scraper_logger)
    def scrap_products_from_beleza_na_web(self) -> List[str]:
        sellers_list = []
        try:
            for url in self.products_urls:
                response = requests.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:79.0) Gecko/20100101 Firefox/79.0'
                    },
                )

                soup = BeautifulSoup(response.content, 'html.parser')
                id_sellers = soup.find_all(
                    'a',
                    class_='btn btn-block btn-primary btn-lg js-add-to-cart',
                )

                for id_seller in id_sellers:
                    sellers = id_seller.get('data-sku')
                    row = json.loads(sellers)[0]
                    '\n'

                    scraper_logger.info(
                        f"Extraindo dados do vendedor Id: {row['seller']['id']} \
                            | Loja: {row['seller']['name']} "
                    )

                    sellers_row = [
                        row['sku'],
                        row['brand'],
                        row['category'],
                        row['name'],
                        row['price'],
                        row['seller']['name'],
                    ]
                    sellers_list.append(sellers_row)
            return sellers_list

        except requests.RequestException as e:
            scraper_logger.exception(e)

    @benchmark_with(scraper_logger)
    @logging_with(scraper_logger)
    def scrap_products_from_marketplace(self) -> List[str]:
        sellers_list = []
        try:
            if self.marketplace == 'BELEZA_NA_WEB':
                sellers_list = self.scrap_products_from_beleza_na_web()
        except requests.RequestException as e:
            scraper_logger.exception(e)

        return sellers_list
