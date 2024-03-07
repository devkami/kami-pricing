import unittest
from unittest.mock import MagicMock, patch

from kami_pricing.pricing_manager import PricingManager


class MockCredentials:
    valid = True


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
    def test_scraping_and_pricing_failure(self, MockScraper, MockPricing):

        MockScraper.return_value.scrap_products_from_marketplace.side_effect = Exception(
            'Scraping error'
        )

        with self.assertRaises(Exception):
            self.pricing_manager.scraping_and_pricing()


if __name__ == '__main__':
    unittest.main()
