import unittest
from unittest.mock import MagicMock, patch

from kami_pricing.pricing_manager import PricingManager


class TestPricingManager(unittest.TestCase):
    @patch('kami_pricing.pricing_manager.AnymarketAPI')
    def setUp(self, MockAnymarketAPI):

        self.mock_anymkt_api = MagicMock()
        MockAnymarketAPI.return_value = self.mock_anymkt_api

        self.pricing_manager = PricingManager(
            company='HAIRPRO', marketplace='BELEZA_NA_WEB'
        )

    def test_init(self):
        self.assertEqual(self.pricing_manager.company, 'HAIRPRO')
        self.assertEqual(self.pricing_manager.marketplace, 'BELEZA_NA_WEB')

    @patch('kami_pricing.pricing_manager.Pricing')
    @patch('kami_pricing.pricing_manager.Scraper')
    def test_scraping_and_pricing_success(self, MockScraper, MockPricing):

        mock_scraper = MockScraper.return_value
        mock_pricing = MockPricing.return_value

        mock_scraper.scrap_products_from_marketplace.return_value = [
            {
                'sku': 'sku1',
                'brand': 'brand1',
                'category': 'category1',
                'name': 'name1',
                'price': 100,
                'seller_name': 'seller_name1',
            },
            {
                'sku': 'sku2',
                'brand': 'brand2',
                'category': 'category2',
                'name': 'name2',
                'price': 200,
                'seller_name': 'seller_name2',
            },
        ]
        mock_pricing.create_dataframes.return_value = MagicMock()
        mock_pricing.drop_inactives.return_value = MagicMock()
        mock_pricing.ebitda_proccess.return_value = MagicMock()
        mock_pricing.pricing.return_value = MagicMock()

        result = self.pricing_manager.scraping_and_pricing()
        self.assertIsNotNone(result)

    @patch('kami_pricing.pricing_manager.Pricing')
    @patch('kami_pricing.pricing_manager.Scraper')
    def test_scraping_and_pricing_failure(self, MockScraper, MockPricing):

        MockScraper.return_value.scrap_products_from_marketplace.side_effect = Exception(
            'Scraping error'
        )

        with self.assertRaises(Exception):
            self.pricing_manager.scraping_and_pricing()


if __name__ == '__main__':
    unittest.main()
