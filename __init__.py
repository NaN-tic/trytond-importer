# This file is part importer module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import importer
from . import party
from . import product
from . import sale
from . import sale_discount
from . import purchase
from . import stock
from . import account
from . import crop
from . import lot
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
        importer.ExcelTemplate,
        module='importer', type_='report')
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
        purchase.Importer,
        purchase.ImporterPurchase,
        purchase.ImporterProductSupplier,
        depends=['purchase'],
        module='importer', type_='model')
    Pool.register(
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
        depends=['account_invoice'],
        module='importer', type_='model')
    Pool.register(
        agronomics.Importer,
        agronomics.ImporterProductAgronomics,
        depends=['agronomics'],
    Pool.register(
        order_point.Importer,
        order_point.ImporterOrderPoint,
        depends=['stock_supply'],
        module='importer', type_='model')
