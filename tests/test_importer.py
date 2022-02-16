# This file is part importer module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import json
import datetime
from xmlrpc.client import DateTime
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.modules.importer.importer import Data
from trytond.modules.company.tests import create_company
from trytond.modules.account.tests import create_chart
from trytond.modules.account.tests import get_fiscalyear
from trytond.modules.account_invoice.tests import set_invoice_sequences

class ImporterTestCase(ModuleTestCase):
    'Test Importer module'
    module = 'importer'

    def activate_module(self, name):
        pool = Pool()
        Module = pool.get('ir.module')
        ActivateUpgrade = pool.get('ir.module.activate_upgrade', type='wizard')

        modules = Module.search([('name', '=', name)], limit=1)
        Module.activate(modules)

        instance_id, _, _ = ActivateUpgrade.create()
        ActivateUpgrade(instance_id).transition_upgrade()
        ActivateUpgrade.delete(instance_id)

        transaction = Transaction()
        transaction.commit()

    def import_(self, method, records):
        pool = Pool()
        Importer = pool.get('importer')

        importer = Importer()
        importer.name = 'Importer'
        importer.method = method
        importer.data_source = 'text'
        importer.text_data = json.dumps(records)
        importer.has_header = True
        importer.use_header = True
        importer.save()

        fields = records[0].keys()
        for column in importer.columns:
            if column.field.name in fields:
                column.name = column.field.name
                column.save()

        data = Data('text', None, json.dumps(records), None)
        importer.data_to_records(data.get_data())

    @with_transaction()
    def test_party(self):
        pool = Pool()

        self.activate_module('party')
        self.import_('party', [{
                'name': 'nan-tic',
                'street': 'les paus',
                'city': 'Sabadell',
                'code': 'NA',
                }])
        Party = pool.get('party.party')
        self.assertEqual(len(Party.search([])), 1)

    @with_transaction()
    def test_product(self):
        pool = Pool()

        self.activate_module('product')
        self.activate_module('sale')
        self.activate_module('purchase')

        Category = pool.get('product.category')
        category = Category()
        category.name = 'Actiu Leasing'
        category.save()

        self.import_('product', [{
                'name': 'Aigua',
                'variant_suffix_code': 'A',
                'template_code': '0001',
                'account_category': category.name,
                'purchasable': 'True',
                'salable': 'True'
                }])
        Product = pool.get('product.product')
        self.assertEqual(len(Product.search([])), 1)

        self.import_('product_codes', [{
                'code': 'xxx',
                'variant_code': '0001A',
                'type_': None,
                }])
        Identifier = pool.get('product.identifier')
        self.assertEqual(len(Identifier.search([])), 1)


        self.activate_module('account_invoice')
        self.activate_module('account_code_digits')

        company = create_company()
        create_chart(company)

        Account = pool.get('account.account')
        accounts = Account.search([])

        for index,account in enumerate(accounts):
                account.code = '000'+str(index+1)
        Account.save(accounts)
        Transaction().set_context(company=company.id)

        self.import_('invoice', [{
                'party_name': company.party.name,
                'invoice_type': 'in',
                'journal': 'EXP',
                'currency': company.currency.name,
                }])

        Invoice = pool.get('account.invoice')
        self.assertEqual(len(Invoice.search([])), 1)


        FiscalYear = pool.get('account.fiscalyear')
        fiscalyear = get_fiscalyear(company)
        set_invoice_sequences(fiscalyear)
        fiscalyear.save()
        FiscalYear.create_period([fiscalyear])

        Date = Pool().get('ir.date')
        today = Date.today()

        self.import_('account_move_account_party', [{
                'account_name': 'Despeses Desembre Maria Eugenia',
                'party_name': company.party.name,
                'state': 'draft',
                'account_code': '43000001',
                'debit': 10000,
                'credit': 0,
                'effective_date': today.strftime('%Y-%m-%d'),
                'number': '20117',
                'journal_code': 'EXP',
                }])

        Move = pool.get('account.move')
        self.assertEqual(len(Move.search([])), 1)

        self.activate_module('stock')

        self.import_('location', [{
                'name': 'Estanteria 3Z',
                'code': '1245AVXS',
                }])

        Location = pool.get('stock.location')
        self.assertEqual(len(Location.search([])), 9)


        self.import_('sale', [{
                'party_name': company.party.name,
                'currency': company.currency.name,
                'shipment_method': 'manual',
                'invoice_method': 'manual',
                'state': 'draft',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'sale_number': '164664'
                }])

        Sale = pool.get('sale.sale')
        self.assertEqual(len(Sale.search([])), 1)
        sale, = Sale.search([])
        self.assertEqual(len(sale.lines), 1)


        self.import_('purchase', [{
                'party_name': company.party.name,
                'date': today.strftime('%Y-%m-%d'),
                'state': 'draft',
                'invoice_method': 'manual',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'purchase_number': '164643'
                }])

        Purchase = pool.get('purchase.purchase')
        self.assertEqual(len(Purchase.search([])), 1)
        purchase, = Purchase.search([])
        self.assertEqual(len(purchase.lines), 1)


        self.import_('purchase_product_supplier', [{
                'party_name': company.party.name,
                'party_code': company.party.code,
                'currency': company.currency.name,
                'product_code': '0001A',
                'quantity': 100,
                'unit_price': 13.75,
                'template_code':411,
                'code': '4324'
                }])

        ProductSupplier = pool.get('purchase.product_supplier')
        self.assertEqual(len(ProductSupplier.search([])), 1)
        product_supplier, = ProductSupplier.search([])
        self.assertEqual(len(product_supplier.prices), 1)

def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ImporterTestCase))
    return suite
