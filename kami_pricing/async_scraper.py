import json
import logging
from typing import List
import asyncio
from aiohttp import ClientSession
from aiocache import Cache
from bs4 import BeautifulSoup

from kami_logging import benchmark_with, logging_with

scraper_logger = logging.getLogger('async_scraper')

class AsyncScraper:
    def __init__(
            self,
            marketplace: str = 'BELEZA_NA_WEB',
            products_urls: List[str] = None
    ):
        self.marketplace = marketplace
        self.products_urls = products_urls
        self.cache = Cache(Cache.MEMORY)
        self.session = None

    async def fetch(self, url: str) -> str:
        async with self.session.get(url) as response:
            return await response.text()

    @benchmark_with(scraper_logger)
    @logging_with(scraper_logger)
    async def scrap_products_from_beleza_na_web(self) -> List[str]:
        sellers_list = []
        try:
            for url in self.products_urls:                
                cached_response = await self.cache.get(url)
                if not cached_response:
                    response_content = await self.fetch(url)                    
                    await self.cache.set(url, response_content)
                else:
                    response_content = cached_response

                soup = BeautifulSoup(response_content, 'html.parser')
                id_sellers = soup.find_all(
                    'a',
                    class_='btn btn-block btn-primary btn-lg js-add-to-cart',
                )

                for id_seller in id_sellers:
                    sellers = id_seller.get('data-sku')
                    row = json.loads(sellers)[0]
                    '\n'

                    scraper_logger.info(
                        f"seller id: {row['seller']['id']}, seler name: {row['seller']['name']}"
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

        except Exception as e:
            scraper_logger.exception(str(e))

    @benchmark_with(scraper_logger)
    @logging_with(scraper_logger)
    async def scrap_products_from_marketplace(self) -> List[str]:
        sellers_list = []
        try:
            if self.marketplace == 'BELEZA_NA_WEB':
                sellers_list = await self.scrap_products_from_beleza_na_web()
        except Exception as e:
            scraper_logger.exception(str(e))

        return sellers_list

    async def run(self):
        self.session = ClientSession()
        try:            
            result = await self.scrap_products_from_marketplace()
            print(result)
        finally:
            await self.session.close()