import json
import unittest

from proteus import Model, Wizard, config as pconfig
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
        current_config = pconfig.get_config()

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

        ProductIdentifier = Model.get('product.identifier')
        identifier = ProductIdentifier()
        identifier.product = product
        identifier.type = 'brand'
        identifier.code = 'OLD-BRAND'
        identifier.save()
        identifier = ProductIdentifier()
        identifier.product = product
        identifier.type = 'mpn'
        identifier.code = 'OLD-MPN'
        identifier.save()
        identifier = ProductIdentifier()
        identifier.product = product
        identifier.type = 'ean'
        identifier.code = '4006381333931'
        identifier.save()

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
        Importer.update_columns([importer], context=current_config.context)

        fields = records[0].keys()
        for column in importer.columns:
            if column.field.name in fields:
                column.name = column.field.name
                column.save()

        Wizard('importer.import', [importer])

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

        importer = Importer()
        importer.name = 'Importer Identifiers'
        importer.method = 'product'
        importer.data_source = 'text'
        records = [{
            'template_code': template.code,
            'variant_code': product.code,
            'name': template.name,
            'uom': unit.name,
            'type_': template.type,
            'brand_product_identifier': 'BRAND-1, BRAND-2',
            'manufacturer_part_identifier': 'MPN-1, MPN-2',
            'ean': '5901234123457, 9780306406157',
        }]
        importer.text_data = json.dumps(records)
        importer.has_header = True
        importer.use_header = True
        importer.save()
        Importer.update_columns([importer], context=current_config.context)

        fields = records[0].keys()
        for column in importer.columns:
            if column.field.name in fields:
                column.name = column.field.name
                column.save()

        Wizard('importer.import', [importer])

        identifiers = ProductIdentifier.find([
            ('product', '=', product.id),
        ])
        by_type = {}
        for identifier in identifiers:
            by_type.setdefault(identifier.type, []).append(identifier.code)
        self.assertEqual(sorted(by_type['brand']), ['BRAND-1', 'BRAND-2'])
        self.assertEqual(sorted(by_type['mpn']), ['MPN-1', 'MPN-2'])
        self.assertEqual(sorted(by_type['ean']), [
            '5901234123457',
            '9780306406157',
        ])
