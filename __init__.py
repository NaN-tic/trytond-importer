# This file is part importer module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import importer
from . import party
from . import product
from . import sale
from . import purchase
from . import stock

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
        depends=['product'],
        module='importer', type_='model')
    Pool.register(
        sale.Importer,
        sale.ImporterSale,
        depends=['sale'],
        module='importer', type_='model')
    Pool.register(
        purchase.Importer,
        purchase.ImporterPurchase,
        depends=['purchase'],
        module='importer', type_='model')
    Pool.register(
        stock.Importer,
        stock.ImporterLot,
        depends=['stock_lot'],
        module='importer', type_='model')
