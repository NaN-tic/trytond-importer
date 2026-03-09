# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.modules.importer.importer import DataExtractor
from trytond.modules.company.tests import create_company


class ImporterTestCase(ModuleTestCase):
    'Test Importer module'
    module = 'importer'
    extras = ['party', 'company', 'product', 'sale', 'purchase',
        'account_invoice', 'account_code_digits', 'stock',
        'product_price_list', 'user_role', 'bank', 'bank_es']

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
        Importer.update_columns([importer])

        if records:
            fields = records[0].keys()
            for column in importer.columns:
                if column.field.name in fields:
                    column.name = column.field.name
                    column.save()

        data = DataExtractor('text', None, json.dumps(records), None)
        data.load()
        importer.data_to_records(data)

    @with_transaction()
    def test_party(self):
        pool = Pool()

        self.import_('sequence', [{
                'name': 'Test',
                'sequence_type': 'Party',
                'prefix': 'X',
                'suffix': 'Y',
                'padding': 4,
                'number_next': 1,
                }])
        self.import_('party', [{
                'name': 'NaN-tic',
                'street': 'Les Paus, 98 Local 2',
                'city': 'Sabadell',
                'code': '08202',
                }])
        Party = pool.get('party.party')
        self.assertEqual(len(Party.search([])), 1)

    @with_transaction()
    def test_product(self):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()

        self.import_('language', [{
                'code': 'ca',
                'translatable': True,
                }])
        Language = pool.get('ir.lang')
        self.assertEqual(len(Language.search([('translatable', '=', True)])), 2)

        company = create_company()

        self.import_('employee', [{
                'name': 'Supervisor',
                'company': company.party.name,
                'from_date': None,
                'to_date': None,
                'supervisor': None,
                }, {
                'name': 'Supervised',
                'company': company.party.name,
                'from_date': today.strftime('%Y-%m-%d'),
                'to_date': today.strftime('%Y-%m-%d'),
                'supervisor': 'Supervisor',
                }])
        Employee = pool.get('company.employee')

        employees = [x.party.name for x in Employee.search([],
            order=[('party.name', 'ASC')])]
        self.assertEqual(employees, ['Supervised', 'Supervisor'])

        self.import_('role', [{
                'name': 'Test',
                'groups': 'Sales,Purchase',
                }])

        self.import_('user', [{
                'name': 'User',
                'login': 'user',
                'email': 'user@nan-tic.com',
                'password': '0123456789',
                'language_code': 'ca',
                'groups': 'Administration',
                'roles': 'Test',
                'companies': company.party.name,
                'company': company.party.name,
                'employees': 'Supervised',
                'employee': 'Supervised',
                }])


        self.import_('account_create_chart', [{
                'company_name': company.party.name,
                'chart_name': 'Universal Chart of Accounts',
                }])

        Transaction().set_context(company=company.id)

        Party = pool.get('party.party')

        self.import_('party', [{
                'company': company.party.name,
                'name': 'Party in company',
                }])

        Bank = pool.get('bank')
        self.import_('bank', [{
                    'name': 'Sabadell',
                    'bic': 'BSABESBBXXX',
                    }])
        bank, = Bank.search([])
        self.assertEqual(bank.bic, 'BSABESBBXXX')
        Bank.delete([bank])

        # Spain must be created before bank_es can be imported
        Country = pool.get('country.country')
        spain = Country()
        spain.name = 'Spain'
        spain.code = 'ES'
        spain.save()

        self.import_('spanish_bank', [])
        banks = Bank.search([])
        self.assertGreater(len(banks), 10)

        Category = pool.get('product.category')
        category = Category()
        category.name = 'Actiu Leasing'
        category.accounting = True
        category.save()

        self.import_('product', [{
                'company': company.party.name,
                'name': 'Aigua',
                'variant_suffix_code': 'A',
                'template_code': '0001',
                'account_category': category.name,
                'purchasable': 'True',
                'salable': 'True',
                'supplier_unit_price': '5',
                'cost_price': '5',
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

        self.import_('price_list', [{
                'name': "Price List",
                'company_name': company.rec_name,
                'tax_included': True,
                'category': None,
                'product_code': '0001A',
                'quantity': 100,
                'formula': '5.12',
                }])
        PriceList = pool.get('product.price_list')
        self.assertEqual(len(PriceList.search([])), 1)

        self.import_('invoice', [{
                'party_name': company.party.name,
                'invoice_type': 'in',
                'journal': 'EXP',
                'currency': company.currency.name,
                }])

        Invoice = pool.get('account.invoice')
        self.assertEqual(len(Invoice.search([])), 1)

        # Current year
        self.import_('sequence', [{
                'name': 'Account Move',
                'sequence_type': 'Account Move',
                'strict': '1',
                }])
        self.import_('sequence', [{
                'name': 'Invoice',
                'sequence_type': 'Invoice',
                'strict': '1',
                }])
        year = Date.today().year
        self.import_('account_fiscalyear', [{
                'name': str(year),
                'company_name': company.party.name,
                'start_date': str(year) + '-01-01',
                'end_date': str(year) + '-12-31',
                'move_sequence_name': 'Account Move',
                'out_invoice_sequence_name': 'Invoice',
                'in_invoice_sequence_name': 'Invoice',
                'out_credit_note_sequence_name': 'Invoice',
                'in_credit_note_sequence_name': 'Invoice',
                }])

        # In this test, we dont have the spansih account tree, we cant use
        # accounts like '43000001', so we adapt the code to use the same
        # structure
        # TODO: in 7.4 and above, change the account code to adapt to the new
        # core defaults accounts
        self.import_('account_move_account_party', [{
                'account_name': 'Despeses Desembre Maria Eugenia',
                'party_name': company.party.name,
                'state': 'draft',
                'account_code': '5.1.5000',
                'debit': 10000,
                'credit': 0,
                'effective_date': today.strftime('%Y-%m-%d'),
                'number': '20117',
                'journal_code': 'EXP',
                }])

        Move = pool.get('account.move')
        self.assertEqual(len(Move.search([])), 1)

        self.import_('location', [{
                'name': 'Estanteria 3Z',
                'code': '1245AVXS',
                }])

        Location = pool.get('stock.location')
        self.assertEqual(len(Location.search([])), 9)

        # sales
        self.import_('sale', [{
                'party_name': company.party.name,
                'currency': company.currency.name,
                'shipment_method': 'manual',
                'invoice_method': 'manual',
                'state': 'draft',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'sale_number': '164664-A'
                }, {
                'party_name': company.party.name,
                'currency': company.currency.name,
                'shipment_method': 'manual',
                'invoice_method': 'manual',
                'state': 'quote',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'sale_number': '164664-B'
                }, {
                'party_name': company.party.name,
                'currency': company.currency.name,
                'shipment_method': 'manual',
                'invoice_method': 'manual',
                'state': 'confirm',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'sale_number': '164664-C'
                }])

        Sale = pool.get('sale.sale')
        sales = Sale.search([])
        self.assertEqual(len(sales), 3)
        sale1, sale2, sale3 = sales
        self.assertEqual(len(sale1.lines), 1)
        self.assertEqual(
            sorted([sale1.state, sale2.state, sale3.state]),
            ['confirmed', 'draft', 'quotation'])

        # purchases
        self.import_('party', [{
                'name': 'supplier1'
                }, {
                'name': 'supplier2'
                }, {
                'name': 'supplier3'
                }])
        supplier1, supplier2, supplier3 = Party.search([], limit=3, order=[('id', 'desc')])

        self.import_('purchase', [{
                'party_name': supplier1.name,
                'date': today.strftime('%Y-%m-%d'),
                'state': 'draft',
                'invoice_method': 'manual',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'purchase_number': '164643-A'
                }, {
                'party_name': supplier2.name,
                'date': today.strftime('%Y-%m-%d'),
                'state': 'quote',
                'invoice_method': 'manual',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'purchase_number': '164643-B'
                }, {
                'party_name': supplier3.name,
                'date': today.strftime('%Y-%m-%d'),
                'state': 'confirm',
                'invoice_method': 'manual',
                'product_code': '0001A',
                'quantity': 5,
                'unit_price': 0.75,
                'purchase_number': '164643-C'
                }])

        Purchase = pool.get('purchase.purchase')
        purchases = Purchase.search([])
        self.assertEqual(len(purchases), 3)
        purchase1, purchase2, purchase3 = purchases
        self.assertEqual(len(purchase1.lines), 1)
        self.assertEqual(
            sorted([purchase1.state, purchase2.state, purchase3.state]),
            ['confirmed', 'draft', 'quotation'])

        # purchase product supplier
        self.import_('purchase_product_supplier', [{
                'party_name': company.party.name,
                'party_code': company.party.code,
                'currency': company.currency.name,
                'product_code': '0001A',
                'quantity': 100,
                'unit_price': '13.75',
                'template_code': 411,
                'code': '4324'
                }])

        ProductSupplier = pool.get('purchase.product_supplier')
        self.assertEqual(len(ProductSupplier.search([])), 1)
        product_supplier, = ProductSupplier.search([])
        self.assertEqual(len(product_supplier.prices), 1)


del ModuleTestCase
