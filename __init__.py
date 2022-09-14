# This file is part importer module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import importer
from . import party
from . import price_list
from . import product
from . import sale
from . import sale_discount
from . import purchase
from . import stock
from . import account
from . import lot
from . import crop
from . import farm
from . import invoice
from . import agronomics
from . import order_point

def register():
    Pool.register(
        importer.Importer,
        importer.ImporterColumn,
        importer.ImportAsk,
        module='importer', type_='model')
    Pool.register(
        importer.AskAndImport,
        importer.Import,
        module='importer', type_='wizard')
    Pool.register(
        party.Importer,
        party.ImporterParty,
        depends=['party'],
        module='importer', type_='model')
    Pool.register(
        product.Importer,
        product.ImporterProduct,
        product.ImporterProductCodes,
        depends=['product'],
        module='importer', type_='model')
    Pool.register(
        price_list.Importer,
        price_list.ImporterPriceList,
        depends=['product_price_list'],
        module='importer', type_='model')
    Pool.register(
        sale.Importer,
        sale.ImporterSale,
        depends=['sale'],
        module='importer', type_='model')
    Pool.register(
        sale_discount.Importer,
        sale_discount.ImporterSale,
        depends=['sale_discount'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterPurchaseDepends,
        purchase.Importer,
        purchase.ImporterPurchase,
        purchase.ImporterProductSupplier,
        depends=['purchase'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterPartyStockDepends,
        stock.Importer,
        stock.ImporterLocation,
        stock.ImporterStockMove,
        depends=['stock'],
        module='importer', type_='model')
    Pool.register(
        lot.Importer,
        lot.ImporterLot,
        depends=['stock_lot'],
        module='importer', type_='model')
    Pool.register(
        account.Importer,
        account.ImporterAccountMove,
        party.ImporterAccountDepends,
        depends=['account'],
        module='importer', type_='model')
    Pool.register(
        farm.Importer,
        farm.ImporterFarmMoveEvent,
        farm.ImporterFarmRemovalEvent,
        farm.ImporterFarmAnimal,
        farm.ImporterFarmMedicationEvent,
        farm.ImporterFarmInseminationEvent,
        farm.ImporterFarmPregnancyDiagnosisEvent,
        farm.ImporterFarmAbortEvent,
        farm.ImporterFarmFarrowingEvent,
        farm.ImporterFarmWeaningEvent,
        farm.ImporterFarmTransformationEvent,
        farm.ImporterFarmReclassificationEvent,
        depends=['farm'],
        module='importer', type_='model')
    Pool.register(
        crop.Importer,
        crop.ImporterParcel,
        crop.ImporterPlantation,
        depends=['agronomics'],
        module='importer', type_='model')
    Pool.register(
        invoice.Importer,
        invoice.ImporterInvoice,
        party.ImporterPartyInvoiceDepends,
        depends=['account_invoice'],
        module='importer', type_='model')
    Pool.register(
        agronomics.Importer,
        agronomics.ImporterProductAgronomics,
        depends=['agronomics'],
        module='importer', type_='model')
    Pool.register(
        order_point.Importer,
        order_point.ImporterOrderPoint,
        depends=['stock_supply'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterCustomerDepends,
        depends=['party_customer'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterSupplierDepends,
        depends=['party_supplier'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterCommissionDepends,
        depends=['commission'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterIncotermDepends,
        depends=['incoterm'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterIncotermPurchaseDepends,
        depends=['purchase_incoterm'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterAEATSIIDepends,
        depends=['aeat_sii'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterCompanyBankDepends,
        depends=['company_bank'],
        module='importer', type_='model')