import json
import logging
from dataclasses import dataclass, field
from os import path
from typing import Union

import numpy as np
import pandas as pd
from kami_gsuite.kami_gsheet import KamiGsheet
from kami_logging import benchmark_with, logging_with

from kami_pricing.constant import (
    COLUMNS_ALL_SELLER,
    COLUMNS_DIFERENCE,
    COLUMNS_EXCEPT_HAIRPRO,
    GOOGLE_API_CREDENTIALS,
    ID_HAIRPRO_SHEET,
)

pricing_logger = logging.getLogger('pricing')


class PricingError(Exception):
    pass


@dataclass
class Pricing:
    multiplier_commission: float = (0.15,)
    multiplier_admin: float = (0.05,)
    multiplier_reverse: float = (0.003,)
    limit_rate_ebitda: float = (4.0,)
    increment_price_new: float = (0.10,)
    gsheet_id: str = (ID_HAIRPRO_SHEET,)
    gsheet_name: str = ('pricing',)
    ebit_sheet_name: str = ('ebit',)
    gsheet: KamiGsheet = field(init=False)

    def __post_init__(self):
        self.gsheet = KamiGsheet(
            api_version='v4', credentials_path=GOOGLE_API_CREDENTIALS
        )

    @classmethod
    def _validate_json_data(cls, json_data: dict):
        required_keys = [
            'multiplier_commission',
            'multiplier_admin',
            'multiplier_reverse',
            'limit_rate_ebitda',
            'increment_price_new',
            'gsheet_id',
            'gsheet_name',
            'ebit_sheet_name',
        ]
        missing_keys = [key for key in required_keys if key not in json_data]
        if missing_keys:
            raise PricingError(
                f"JSON data must contain the following keys: {', '.join(missing_keys)}"
            )

    @classmethod
    def _load_json_from_file(cls, file_path: str):
        try:
            with open(file_path, 'r') as json_file:
                json_data = json.load(json_file)
        except Exception as e:
            raise PricingError(f'Failed to load JSON file: {e}')
        return json_data

    @classmethod
    def _load_json_from_string(cls, json_string: str):
        try:
            json_data = json.loads(json_string)
        except Exception as e:
            raise PricingError(f'Failed to load JSON string: {e}')
        return json_data

    @classmethod
    def from_json(cls, json_data: Union[str, dict]):
        if isinstance(json_data, str) and path.isfile(json_data):
            try:
                json_data = cls._load_json_from_file(json_data)
            except PricingError as e:
                raise e
        elif isinstance(json_data, str):
            try:
                json_data = cls._load_json_from_string(json_data)
            except PricingError as e:
                raise e
        elif isinstance(json_data, dict):
            pass
        else:
            raise PricingError('Invalid JSON data format.')

        cls._validate_json_data(json_data)

        return cls(**json_data)

    def calc_ebitda(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['COMISSÃO'] = round(
                df['special_price'] * self.multiplier_commission, 2
            )
            df['ADMIN'] = round(df['special_price'] * self.multiplier_admin, 2)
            df['REVERSA'] = round(
                df['special_price'] * self.multiplier_reverse, 2
            )
            df['EBITDA R$'] = (
                df['special_price']
                - df['CUSTO']
                - df['FRETE']
                - df['INSUMO']
                - df['COMISSÃO']
                - df['ADMIN']
                - df['REVERSA']
            )
            df['EBITDA %'] = (
                round(df['EBITDA R$'] / df['special_price'], 3) * 100
            )
            df = df.dropna(subset=['EBITDA R$'], axis=0, how='any')
            df = df.reset_index()
            return df
        except ZeroDivisionError:
            pricing_logger.error(
                'Division by zero encountered while calculating percentages.'
            )
        except Exception as e:
            pricing_logger.error(f'An unexpected error occurred: {str(e)}')
            return None

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def pricing(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.calc_ebitda(df)
        try:
            for idx in range(0, len(df['special_price'])):
                while df.loc[idx, 'EBITDA %'] < self.limit_rate_ebitda:
                    df.loc[idx, 'special_price'] += self.increment_price_new
                    df.loc[idx, 'COMISSÃO'] = round(
                        df.loc[idx, 'special_price']
                        * self.multiplier_commission,
                        2,
                    )
                    df.loc[idx, 'ADMIN'] = round(
                        df.loc[idx, 'special_price'] * self.multiplier_admin,
                        2,
                    )
                    df.loc[idx, 'REVERSA'] = round(
                        df.loc[idx, 'special_price'] * self.multiplier_reverse,
                        2,
                    )
                    df.loc[idx, 'EBITDA R$'] = (
                        df.loc[idx, 'special_price']
                        - df.loc[idx, 'CUSTO']
                        - df.loc[idx, 'COMISSÃO']
                        - df.loc[idx, 'FRETE']
                        - df.loc[idx, 'ADMIN']
                        - df.loc[idx, 'INSUMO']
                        - df.loc[idx, 'REVERSA']
                    )
                    df.loc[idx, 'EBITDA %'] = (
                        round(
                            df.loc[idx, 'EBITDA R$']
                            / df.loc[idx, 'special_price'],
                            2,
                        )
                        * 100
                    )
                else:
                    pricing_logger.info(
                        f"The sku {df.loc[idx, 'sku (*)']} with a price of {df.loc[idx, 'special_price']} has an ebitda of {df.loc[idx, 'EBITDA %']}"
                    )
        except Exception as e:
            pricing_logger.error(f'An unexpected error occurred: {str(e)}')
            return None

        return df

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def create_dataframes(
        self, sellers_list: list, products_df: pd.DataFrame
    ) -> pd.DataFrame:
        df_sellers_df_list = pd.DataFrame(
            sellers_list, columns=COLUMNS_ALL_SELLER
        )
        df_sellers_df_list.drop_duplicates(keep='first', inplace=True)
        df_sellers_df_list['seller_name'] = df_sellers_df_list[
            'seller_name'
        ].astype(str)
        hairpro_df = df_sellers_df_list.loc[
            df_sellers_df_list['seller_name'] == 'HAIRPRO'
        ]
        except_hairpro_df = df_sellers_df_list.drop(
            df_sellers_df_list[
                df_sellers_df_list['seller_name'].str.contains('HAIRPRO')
            ].index
        )
        except_hairpro_df = pd.DataFrame(
            except_hairpro_df, columns=COLUMNS_EXCEPT_HAIRPRO
        )

        sugest_price = except_hairpro_df.groupby('sku')['price'].idxmin()
        except_hairpro_df = except_hairpro_df.loc[sugest_price]

        difference_price_df = pd.DataFrame(
            hairpro_df, columns=COLUMNS_DIFERENCE
        )

        for i in hairpro_df['sku']:
            for j in except_hairpro_df['sku']:
                if i == j:
                    difference_price_df.loc[
                        difference_price_df['sku'] == i, 'competitor_price'
                    ] = except_hairpro_df.loc[
                        except_hairpro_df['sku'] == j, 'price'
                    ].values[
                        0
                    ]
                    difference_price_df['difference_price'] = (
                        difference_price_df['competitor_price']
                        - difference_price_df['price']
                        - 0.10
                    )
                    difference_price_df[
                        'difference_price'
                    ] = difference_price_df['difference_price'].round(6)
                # quando difference_price_df['competitor_price'] for zero e sua serie for ambigua, sugerir um preco de 10% maior
                # e arrendondar para 2 casas decimais o preco sugerido
                if (
                    difference_price_df['competitor_price']
                    .isnull()
                    .values.any()
                ):
                    difference_price_df['suggest_price'] = difference_price_df[
                        'price'
                    ].round(6)

                # quando o preço da Hairpro for maior que o preço do concorrente, sugerir o preço de 0,10 centavos a menos
                # que o preço do concorrente e arrendondar para 2 casas decimais o preco sugerido
                if (
                    difference_price_df['price'].min()
                    < difference_price_df['competitor_price'].max()
                ):
                    difference_price_df['suggest_price'] = (
                        difference_price_df['competitor_price'].round(6) - 0.10
                    )

                # percentual de diferença entre o preço da Hairpro e o preço do concorrente
                difference_price_df['ganho_%'] = (
                    difference_price_df['suggest_price']
                    / difference_price_df['price']
                ) - 1
                difference_price_df['ganho_%'] = (
                    difference_price_df['ganho_%'].round(2) * 100
                )

        sku_sellers = products_df.rename(
            columns={'sku_seller': 'sku_kami', 'sku_beleza': 'sku'}
        )
        sku_sellers = sku_sellers[['sku', 'sku_kami']]
        pricing_result = difference_price_df.merge(sku_sellers, how='left')
        df_pricing = pricing_result[
            ['sku_kami', 'suggest_price', 'competitor_price']
        ]
        df_pricing = df_pricing.dropna()
        df_pricing = df_pricing.rename(
            columns={'suggest_price': 'special_price', 'sku_kami': 'sku (*)'}
        )

        return df_pricing

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def ebitda_proccess(self, df: pd.DataFrame):
        self.gsheet.clear_range(self.gsheet_id, f'{self.ebit_sheet_name}!A2:B')

        df = df[['sku (*)', 'special_price']]

        self.gsheet.append_dataframe(
            df, self.gsheet_id, f'{self.ebit_sheet_name}!A2:B'
        )
        df_ebitda = self.gsheet.convert_range_to_dataframe(
            self.gsheet_id, f'{self.ebit_sheet_name}!A1:E'
        )
        df_ebitda = df_ebitda.replace('None', np.nan)

        numeric_columns = ['special_price', 'CUSTO', 'FRETE', 'INSUMO']
        df_ebitda[numeric_columns] = df_ebitda[numeric_columns].apply(
            lambda x: pd.to_numeric(
                x.str.replace(',', '.', regex=False), errors='coerce'
            )
        )

        return df_ebitda
