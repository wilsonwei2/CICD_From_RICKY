import os
import json
import logging

from param_store.client import ParamStore
from netsuite.service import RecordRef

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')

#
# This class is introduced to handle the tax code mapping for Frank & Oak for:
#    - Order Integration - CashSale / SalesOrders
#    - Return Integration - CashRefunds / CreditMemos
#    - Appeasements Integration
#
# Depending on a preference, the functions map the given parameters to the tax code which
# is used by Netsuite to calculate the tax again. There are 2 scenarios / logics implemented:
#    - Netsuite is used Avalara to calculate the taxes - aka AVATAX
#    - NewStore maps to the Netsuite tax codes based on the state / country of the user. This is plan B
#      used for the go-live
#
class TaxManager():
    param_store = None
    netsuite_config = {}

    @staticmethod
    def _get_param_store():
        if not TaxManager.param_store:
            TaxManager.param_store = ParamStore(tenant=TENANT,
                                                stage=STAGE)
        return TaxManager.param_store

    @staticmethod
    def _get_netsuite_config():
        # TODO - enable the next line again once the configuration is stable pylint: disable=fixme
        # if not TaxManager.netsuite_config:
        TaxManager.netsuite_config = json.loads(TaxManager._get_param_store().get_param('netsuite'))
        return TaxManager.netsuite_config

    #
    # Standard function to get the tax code id from a preference. This is used
    # mainly if Avalara/Avatax is enabled in Netsuite.
    #
    @staticmethod
    def _get_tax_code_id(currency):
        if currency.lower() == 'usd':
            return TaxManager._get_netsuite_config()['tax_override_us']
        if currency.lower() == 'cad':
            return TaxManager._get_netsuite_config()['tax_override_ca']
        raise ValueError(f"Provided currency, {currency}, not mapped")

    #
    # Returns the Non-Taxable tax code id from a preference.
    #
    @staticmethod
    def _get_not_taxable_id(currency):
        if currency.lower() == 'usd':
            return TaxManager._get_netsuite_config()['not_taxable_us']
        if currency.lower() == 'cad':
            return TaxManager._get_netsuite_config()['not_taxable_ca']
        raise ValueError(f'Provided currency, {currency}, not mapped')


    #
    # Returns the tax code id to be set for the Customer record.
    #
    @staticmethod
    def get_customer_tax_item_id(currency):
        return TaxManager._get_netsuite_config().get('customer_tax_item_' + currency.lower(), -1)


    #
    # Gets the Netsuite tax code id for CashSale / SalesOrder Items.
    #
    @staticmethod
    def get_order_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for CashRefund / CreditMemo Items.
    #
    @staticmethod
    def get_refund_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for the Appeasment Item (basically a non-inventory item) for
    # CashRefunds.
    #
    @staticmethod
    def get_appeasement_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency)

    #
    # Gets the Netsuite tax code id for the CashSale / SalesOrder Payment Items.
    #
    @staticmethod
    def get_order_payment_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for the CashRefund / CreditMemo Payment Items.
    #
    @staticmethod
    def get_refund_payment_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for the Appeasment Payment Item for
    # CashRefunds.
    #
    @staticmethod
    def get_appeasement_payment_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency)

    #
    # Gets the Netsuite tax code id for the Discount items on CashSale / SalesOrder.
    #
    @staticmethod
    def get_discount_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for the Discount items on CashRefund / CreditMemo.
    #
    @staticmethod
    def get_refund_discount_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for the duty items. Note that duties are not used
    # for F&O
    #
    @staticmethod
    def get_duty_item_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the Netsuite tax code id for shipping costs on CashSale / SalesOrder.
    #
    @staticmethod
    def get_shipping_tax_code_id(currency):
        return TaxManager._get_tax_code_id(currency=currency)

    #
    # Gets the tax offset line item. This is vehicle to workaround tax rounding and payment
    # item issues in Netsuite. This item will be added to all SalesOrder / CashSale / CashRefund / CreditMemo
    # transactions, and then removed in Netsuite after the order is injected, to avoid that Netsuite calculates
    # a negative order total. This solutions has been implemented by F&O after three (3) month of
    # hard research.
    #
    @staticmethod
    def get_tax_offset_line_item(currency):
        return {
            'item': RecordRef(internalId=TaxManager._get_netsuite_config()['tax_offset_item_internal_id']),
            'amount': 10000,
            'taxCode': RecordRef(internalId=TaxManager._get_tax_code_id(currency))
        }
