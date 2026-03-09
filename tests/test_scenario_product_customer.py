import json
import unittest

from proteus import Model
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        activate_modules(['importer', 'sale_product_customer'])

        Party = Model.get('party.party')
        party1 = Party(name='Customer 1', code='CUST1')
        party1.save()
        party2 = Party(name='Customer 2', code='CUST2')
        party2.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'Product'
        template.default_uom = unit
        template.type = 'goods'
        template.code = 'PRD'
        template.cost_price_method = 'fixed'
        template.save()
        product, = template.products

        Importer = Model.get('importer')
        importer = Importer()
        importer.name = 'Importer'
        importer.method = 'sale_product_customer'
        importer.data_source = 'text'
        records = [
            {
                'party': party1.code,
                'template': template.code,
                'product': product.code,
                'name': 'Customer Name 1',
                'code': 'C-1',
            },
            {
                'party': party2.code,
                'template': template.code,
                'product': product.code,
                'name': 'Customer Name 2',
                'code': 'C-2',
            },
        ]
        importer.text_data = json.dumps(records)
        importer.has_header = True
        importer.use_header = True
        importer.save()
        Importer.update_columns([importer])

        fields = records[0].keys()
        for column in importer.columns:
            if column.field.name in fields:
                column.name = column.field.name
                column.save()

        importer.data_to_records()

        ProductCustomer = Model.get('sale.product_customer')
        product_customers = ProductCustomer.find([
            ('template', '=', template.id),
            ('product', '=', product.id),
        ])
        self.assertEqual(len(product_customers), 2)
        product_customers = sorted(product_customers,
            key=lambda pc: pc.party.code)
        self.assertEqual(
            [(pc.party.code, pc.name, pc.code) for pc in product_customers],
            [
                ('CUST1', 'Customer Name 1', 'C-1'),
                ('CUST2', 'Customer Name 2', 'C-2'),
            ])
