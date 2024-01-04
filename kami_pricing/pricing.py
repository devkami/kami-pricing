import logging
from os import path

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


class Pricing:
    def __init__(
        self,
        multiplier_commission: float = 0.15,
        multiplier_admin: float = 0.05,
        multiplier_reverse: float = 0.003,
        limit_rate_ebitda: float = 4.0,
        increment_price_new: float = 0.10,
    ):
        self.multiplier_commission = multiplier_commission
        self.multiplier_admin = multiplier_admin
        self.multiplier_reverse = multiplier_reverse
        self.limit_rate_ebitda = limit_rate_ebitda
        self.increment_price_new = increment_price_new

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
        if df is None:
            return None

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
            return df
        except Exception as e:
            pricing_logger.error(f'An unexpected error occurred: {str(e)}')
            return None

    @benchmark_with(pricing_logger)
    @logging_with(pricing_logger)
    def create_dataframes(self, sellers_list, skus_list) -> pd.DataFrame:
        df_sellers_df_list = pd.DataFrame(
            sellers_list, columns=COLUMNS_ALL_SELLER
        )
        skus_df = pd.DataFrame(skus_list)
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

        sku_sellers = skus_df.rename(
            columns={'SKU Seller': 'sku_kami', 'SKU Beleza': 'sku'}
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
        kg = KamiGsheet(
            api_version='v4',
            credentials_path=GOOGLE_API_CREDENTIALS,
        )
        kg.clear_range(ID_HAIRPRO_SHEET, 'ebit!A2:B')

        df = df[['sku (*)', 'special_price']]

        kg.append_dataframe(df, ID_HAIRPRO_SHEET, 'ebit!A2:B')
        df_ebitda = kg.convert_range_to_dataframe(
            ID_HAIRPRO_SHEET, 'ebit!A1:E'
        )
        df_ebitda = df_ebitda.replace('None', np.nan)

        numeric_columns = ['special_price', 'CUSTO', 'FRETE', 'INSUMO']
        df_ebitda[numeric_columns] = df_ebitda[numeric_columns].apply(
            lambda x: pd.to_numeric(
                x.str.replace(',', '.', regex=False), errors='coerce'
            )
        )

        return df_ebitda

    def drop_inactives(self, df: pd.DataFrame):
        kg = KamiGsheet(
            api_version='v4',
            credentials_path=GOOGLE_API_CREDENTIALS,
        )

        df_active = kg.convert_range_to_dataframe(
            ID_HAIRPRO_SHEET, 'pricing_teste!A1:B'
        )

        df_inactives = df_active.loc[df_active['status'] == 'INATIVO']

        try:
            to_drop_pricing = []
            for sku in df_inactives['sku']:
                to_drop_pricing.extend(df.loc[df['sku (*)'] == sku].index)
            df = df.drop(to_drop_pricing)

            return df
        except Exception as e:
            pricing_logger.exception(str(e))
            return None