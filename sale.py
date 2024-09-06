from datetime import datetime
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.product import round_price
from .tools import ImporterModel, Setup, Cache


class ImporterSale(ImporterModel):
    'Importer Sale'
    __name__ = 'importer.sale'

    reference = fields.Char('Reference')
    date = fields.Date('Date')
    party_name = fields.Char('Party Name')
    party_code = fields.Char('Party Code')
    shipment_party_name = fields.Char('Shipment Party Name')
    shipment_address = fields.Char('Shipment Address Name')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')
    currency = fields.Char('Currency')
    shipment_method = fields.Char('Shipment Method')
    invoice_method = fields.Char('Invoice Method')
    sale_number = fields.Char('Sale Number')
    state = fields.Char('State')

    def import_sale_header(self, record):
        return (self.sale_number, self.reference, self.date,
            self.party_code, self.party_name, self.shipment_party_name,
            self.shipment_address, self.currency)

    def importer_sale(self, sale):
        pass

    def importer_sale_line(self, line):
        pass

    @classmethod
    def importer_start(cls):
        Product = Pool().get('product.product')

        super().importer_start()

        cache = Setup.get().cache
        cache.currencies = Cache('currency.currency', ['name', 'symbol'])
        cache.parties_by_code = Cache('party.party', 'code', context={
                'active_test': False
                })
        cache.parties_by_code = Cache('party.party', 'code', context={
                'active_test': False
                })
        cache.address = Cache('party.address', lambda x: (x.party.id, x.rec_name))
        product_domain = []
        if 'force' not in Setup.get().method and 'salable' in Product._fields:
            product_domain.append(('salable', '=', True))
        cache.products = Cache('product.product', 'code', context={
                'active_test': False
                }, domain=product_domain)

    def importer_create_party(self):
        Party = Pool().get('party.party')

        values = Party.default_get(
                list(Party._fields.keys()), with_rec_name=False)
        party = Party(**values)
        party.name = self.name or self.code
        party.code = self.code
        if 'customer' in Party._fields:
            party.customer = True
        return party

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        setup = Setup.get()
        cache = setup.cache

        force = False
        if 'force' in setup.method:
            force = True

        sale = None
        sales_to_save = []
        lines_to_save = []
        previous_header = None

        to_quote = []
        to_confirm = []
        to_process = []

        default_line_values = Line.default_get(
            list(Line._fields.keys()), with_rec_name=False)

        for record in records:
            setup.current_record = record

            header = record.importer_header()
            if any(header) and header != previous_header:
                previous_header = header
                values = Sale.default_get(
                    list(Sale._fields.keys()), with_rec_name=False)

                if record.sale_number:
                    domain = [('number', '=', record.sale_number)]
                    if record.date:
                        domain += [('sale_date', '=', record.date)]
                    sales = Sale.search(domain, limit=1)
                    if sales:
                        sale = None
                        continue

                sale = Sale(**values)
                sale.party = None
                if record.shipment_method:
                    sale.shipment_method = record.shipment_method
                if record.invoice_method:
                    sale.invoice_method = record.invoice_method
                if record.sale_number:
                    sale.number = record.sale_number
                sale.reference = record.reference
                if isinstance(record.date, datetime):
                    sale.sale_date = record.date.date()
                else:
                    sale.sale_date = record.date

                # sale workflow (states)
                if record.state:
                    if record.state in ('draft', 'cancelled', 'done'):
                        sale.state = record.state
                    elif record.state == 'quote':
                        to_quote += [sale]
                    elif record.state == 'confirm':
                        to_confirm += [sale]
                    elif record.state == 'process':
                        to_process += [sale]

                if record.currency:
                    sale.currency = cache.currencies.get(record.currency)

                party = None
                if record.party_code:
                    party = cache.parties_by_code.get(record.party_code)
                elif record.party_name:
                    party = cache.parties_by_name.get(record.party_name)

                if not party:
                    if not force:
                        continue
                    party = record.importer_create_party()

                sale.party = party
                sale.on_change_party()
                sales_to_save.append((sale, record))

                if record.shipment_party_name:
                    sale.shipment_party = cache.parties_by_name.get(record.shipment_party_name)
                    sale.on_change_shipment_party()

                if record.shipment_address:
                    values = [x.strip() for x in record.shipment_address.split(',')]
                    addresses = []
                    for address in (sale.shipment_party or sale.party).addresses:
                        rec_name = address.rec_name
                        if all([x in rec_name for x in values]):
                            addresses.append(address)
                    if len(addresses) == 1:
                        sale.shipment_address, = addresses

                record.importer_sale(sale)

            if not sale or not sale.party:
                continue

            if record.product_code:
                product = cache.products.get(record.product_code)
                if not product:
                    continue

                template = product.template
                if (force and 'salable' in Product._fields
                        and not product.salable):
                    template.salable = True
                    template.save()

                if (force and 'validated' in Template._fields
                        and not template.validated):
                    template.validated = True
                    template.save()

                line = Line(**default_line_values)
                line.sale = sale
                line.product = product
                line.on_change_product()
                line.quantity = record.quantity
                line.on_change_quantity()
                if 'product_package' in Line._fields:
                    line.product_package = None
                    line.package_quantity = None
                if record.unit_price is not None:
                    line.unit_price = round_price(record.unit_price)
                record.importer_sale_line(line)
                lines_to_save.append((line, record))

        setup.current_record = None
        cls.importer_save(sales_to_save)
        cls.importer_save(lines_to_save)

        to_confirm += to_process
        to_quote += to_confirm
        Sale.quote(to_quote)
        Sale.confirm(to_confirm)
        Sale.process(to_process)
        return [x[0] for x in sales_to_save]


class ImporterSaleConfiguration(ModelView):
    'Importer Sale Configuration'
    __name__ = 'importer.sale.configuration'

    company = fields.Char('Company')
    sale_sequence_prefix = fields.Char("Sale sequence prefix")
    sale_sequence_suffix = fields.Char("Sale sequence suffix")
    sale_sequence_padding = fields.Integer("Sale sequence padding")
    sale_sequence_number_next = fields.Integer("Sale sequence number next")
    sale_invoice_method = fields.Char("Sale invoice method", help='selection|sale.sale|invoice_method')
    sale_shipment_method = fields.Char("Sale shipment method", help='selection|sale.sale|shipment_method')
    sale_process_after = fields.Char("Sale process after")


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'sale': {
                    'string': 'Sale',
                    'model': 'importer.sale',
                    'chunked': False,
                    },
                'sale_force': {
                    'string': 'Sale Create/Fix Party And Products',
                    'model': 'importer.sale',
                    'chunked': False,
                    },
                'sale_configuration': {
                    'string': 'Sale configuration',
                    'model': 'importer.sale.configuration',
                    'chunked': False,
                    },
                })
        return methods

    @classmethod
    def import_sale_configuration(cls, records):
        pool = Pool()

        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("sale.configuration")
        ModelData = pool.get("ir.model.data")
        Company = pool.get("company.company")

        configs = []
        for record in records:
            if record.company:
                company, = Company.search([('party.name', '=', record.company)])
                company_id = company.id
            else:
                company_id = Transaction().context.get('company')
            with Transaction().set_context(company=company_id):
                configuration = Configuration(1)
                configuration.sale_invoice_method = record.sale_invoice_method
                configuration.sale_shipment_method = record.sale_shipment_method
                configuration.sale_process_after = record.sale_process_after

                if record.sale_sequence_padding or record.sale_sequence_number_next:
                    sequence = configuration.sale_sequence

                    if not sequence or (sequence.company and sequence.company.id != company_id):
                        sequence = Sequence()
                        sequence.name = "Sale"
                        configuration.sale_sequence = sequence
                    sequence.company = company_id
                    sequence.sequence_type = ModelData.get_id('sale', 'sequence_type_sale')
                    sequence.prefix = record.sale_sequence_prefix
                    sequence.suffix = record.sale_sequence_suffix
                    sequence.padding = record.sale_sequence_padding
                    sequence.number_next = record.sale_sequence_number_next
                    sequence.save()

                configuration.save()
                configs.append(configuration)

        return configs
