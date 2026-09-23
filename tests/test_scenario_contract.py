import datetime
import json
import unittest
from decimal import Decimal

from proteus import Model, Wizard, config as pconfig
from trytond.modules.company.tests.tools import create_company, get_company
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
        activate_modules(['importer', 'contract', 'contract_document'])
        current_config = pconfig.get_config()
        create_company()
        company = get_company()

        Party = Model.get('party.party')
        party = Party(name='Customer')
        party.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate(name='Service', type='service',
            default_uom=unit, list_price=Decimal('10'))
        template.save()
        product, = template.products

        Service = Model.get('contract.service')
        service = Service(name='Rent', product=product)
        service.save()

        Contract = Model.get('contract')
        contract = Contract(company=company, currency=company.currency,
            party=party, number='C-1',
            freq='monthly', interval=1,
            start_period_date=datetime.date(2025, 1, 1),
            first_invoice_date=datetime.date(2025, 1, 1))
        contract.lines.new(service=service, sequence=10,
            description='Old description', unit_price=Decimal('10'),
            start_date=datetime.date(2025, 1, 1))
        contract.save()

        Importer = Model.get('importer')
        importer = Importer(name='Contracts', method='contract',
            data_source='text', has_header=True, use_header=True,
            text_data=json.dumps([
                {
                    'number': 'C-1',
                    'service': 'Rent',
                    'description': 'Updated description',
                    'unit_price': '25.00',
                    'sequence': 10,
                    'line_type': 'Rent',
                },
                {
                    'number': 'C-2',
                    'party': 'New Customer',
                    'start_period_date': '2025-01-01',
                    'first_invoice_date': '2025-01-01',
                    'service': 'New Service',
                    'description': 'New line',
                    'unit_price': '30.00',
                    'start_date': '2025-01-01',
                    'sequence': 10,
                    'line_type': 'Rent',
                    'payment_term': 'New Payment Term',
                },
            ])
        )
        importer.save()
        Importer.update_columns([importer], context=current_config.context)
        for column in importer.columns:
            if column.field.name in (
                    'number', 'party', 'start_period_date',
                    'first_invoice_date', 'service', 'description',
                    'unit_price', 'start_date', 'sequence', 'line_type',
                    'payment_term'):
                column.name = column.field.name
                column.save()
        Wizard('importer.import', [importer])

        contract = Contract.find([('number', '=', 'C-1')])[0]
        line = contract.lines[0]
        self.assertEqual(line.description, 'Updated description')
        self.assertEqual(line.unit_price, Decimal('25.00'))
        self.assertEqual(line.line_type.name, 'Rent')

        new_contract = Contract.find([('number', '=', 'C-2')])[0]
        self.assertEqual(new_contract.party.name, 'New Customer')
        self.assertEqual(new_contract.payment_term.name, 'New Payment Term')
        self.assertEqual(new_contract.payment_term.lines[0].type, 'remainder')
        self.assertEqual(new_contract.lines[0].description, 'New line')
        Service = Model.get('contract.service')
        self.assertEqual(len(Service.find([('name', '=', 'New Service')])), 1)
