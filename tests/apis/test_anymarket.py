import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from kami_pricing.api.anymarket import AnymarketAPI, AnymarketAPIError


class TestAnymarketAPI(unittest.TestCase):
    def setUp(self):
        self.api = AnymarketAPI()
        self.api.credentials_path = 'credentials.json'

    @patch('builtins.open', mock_open(read_data='{"token": "your_token"}'))
    @patch('json.load')
    def test_set_credentials_success(self, mock_json_load):
        mock_json_load.return_value = {'token': 'your_token'}

        try:
            self.api._set_credentials()
            self.assertEqual(self.api.credentials, {'token': 'your_token'})
        except AnymarketAPIError:
            self.fail('AnymarketAPIError was raised unexpectedly!')

    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_set_credentials_file_not_found(self, mock_error):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api._set_credentials()
        self.assertIn('Credentials file not found', str(context.exception))

    @patch('builtins.open', mock_open(read_data='invalid json'))
    def test_set_credentials_invalid_json_error(self):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api._set_credentials()
        self.assertIn('contains invalid JSON', str(context.exception))

    @patch('builtins.open', side_effect=PermissionError())
    def test_set_credentials_permission_error(self, mock_permission_error):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api._set_credentials()
        self.assertIn(
            'No permission to read credentials file', str(context.exception)
        )

    @patch('builtins.open', mock_open(read_data='{"token": "your_token"'))
    @patch(
        'json.load',
        side_effect=json.JSONDecodeError('Invalid JSON', doc='', pos=0),
    )
    def test_set_credentials_json_decode_error(self, mock_json_load):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api._set_credentials()
        self.assertIn('contains invalid JSON', str(context.exception))

    @patch('builtins.open', side_effect=Exception('Generic error'))
    def test_set_credentials_generic_error(self, mock_error):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api._set_credentials()
        self.assertIn(
            'Failed to get credentials: Generic error', str(context.exception)
        )

    @patch(
        'httpx.Client.get',
        return_value=MagicMock(
            status_code=200, json=lambda: {'success': True}
        ),
    )
    @patch('kami_pricing.api.anymarket.AnymarketAPI._set_credentials')
    def test_connect_success(self, mock_set_credentials, mock_get):
        self.api.credentials = {'token': 'mock-token'}

        self.api._connect('GET', '/some-endpoint')
        mock_get.assert_called_once()

        self.assertEqual(self.api.result, {'success': True})

    @patch(
        'kami_pricing.api.anymarket.AnymarketAPI._set_credentials',
        autospec=True,
    )
    @patch(
        'httpx.Client.get',
        return_value=MagicMock(
            status_code=200, json=lambda: {'page': {'totalElements': 10}}
        ),
    )
    def test_get_products_quantity_success(
        self, mock_get, mock_set_credentials
    ):
        self.api.credentials = {'token': 'mock-token'}
        total = self.api.get_products_quantity()
        self.assertEqual(total, 10)
        mock_get.assert_called_once_with(
            'https://api.anymarket.com.br/v2/products',
            headers={
                'Content-Type': 'application/json',
                'gumgaToken': 'mock-token',
            },
        )

    @patch('httpx.Client.get', side_effect=Exception('HTTP error'))
    def test_get_products_quantity_http_error(self, mock_get):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api.get_products_quantity()
        self.assertIn('Failed to connect', str(context.exception))

    @patch(
        'kami_pricing.api.anymarket.AnymarketAPI._set_credentials',
        autospec=True,
    )
    @patch(
        'httpx.Client.get',
        return_value=MagicMock(
            status_code=200, json=lambda: {'id': '123', 'name': 'Test Product'}
        ),
    )
    def test_get_product_by_id_success(self, mock_get, mock_set_credentials):
        self.api.credentials = {'token': 'mock-token'}

        product = self.api.get_product_by_id('123')
        mock_get.assert_called_once_with(
            f'https://api.anymarket.com.br/v2/products/123',
            headers={
                'Content-Type': 'application/json',
                'gumgaToken': 'mock-token',
            },
        )

        self.assertEqual(product, {'id': '123', 'name': 'Test Product'})

    @patch('httpx.Client.get', side_effect=Exception('HTTP error'))
    def test_get_products_quantity_http_error(self, mock_get):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api.get_products_quantity()
        self.assertIn('Failed to connect', str(context.exception))

    @patch('kami_pricing.api.anymarket.AnymarketAPI.get_product_by_id')
    def test_get_products_by_ids_success(self, mock_get_product_by_id):
        mock_get_product_by_id.side_effect = [
            {'id': '123', 'name': 'Test Product 1'},
            {'id': '456', 'name': 'Test Product 2'},
        ]
        products = self.api.get_products_by_ids(['123', '456'])
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]['id'], '123')
        self.assertEqual(products[1]['id'], '456')

    @patch('httpx.Client.patch')
    def test_set_product_for_manual_pricing_success(self, mock_patch):
        mock_patch.return_value.json.return_value = {}
        try:
            self.api.set_product_for_manual_pricing('123')
        except Exception as e:
            self.fail(f'Unexpected exception raised: {e}')

    @patch('httpx.Client.put')
    def test_update_price_success(self, mock_put):
        mock_put.return_value.json.return_value = {}
        try:
            self.api.update_price('ad_id', 99.99)
        except Exception as e:
            self.fail(f'Unexpected exception raised: {e}')

    @patch('httpx.Client.put')
    def test_update_price_success(self, mock_put):

        self.api.credentials = {'token': 'mock-token'}

        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {'message': 'Price updated successfully'},
        )

        try:
            self.api.update_price('ad_id', 99.99)
        except Exception as e:
            self.fail(f'Unexpected exception raised: {e}')

        mock_put.assert_called_once()

    @patch(
        'httpx.Client.put',
        side_effect=AnymarketAPIError('Failed to update price'),
    )
    def test_update_price_error(self, mock_put):
        self.api.credentials = {'token': 'mock-token'}
        with self.assertRaises(AnymarketAPIError) as context:
            self.api.update_price('ad_id', 99.99)
        self.assertIn('Failed to update price', str(context.exception))

    def test_update_price_rejects_improper_decimal_places(self):
        with self.assertRaises(AnymarketAPIError) as context:
            self.api.update_price('ad_id', 99.999)
        self.assertIn(
            'New Price: 99.999 must have at most 2 decimal places',
            str(context.exception),
        )


if __name__ == '__main__':
    unittest.main()
