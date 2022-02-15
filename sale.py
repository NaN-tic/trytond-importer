from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from datetime import datetime

class ImporterSale(ModelView):
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
    discount = fields.Numeric('Discount')

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
                })
        return methods

    @classmethod
    def import_sale_header(cls, record):
        return (record.sale_number, record.reference, record.date,
            record.party_code, record.party_name, record.shipment_party_name,
            record.shipment_address, record.currency)

    @classmethod
    def import_sale_force(cls, records):
        return cls.import_sale(records, force=True)


    @classmethod
    def import_sale(cls, records, force=False):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Address = pool.get('party.address')
        Currency = pool.get('currency.currency')

        start = datetime.now()
        exp = Decimal(str(10.0 ** -Line.unit_price.digits[1]))

        currencies = {x.name: x for x in Currency.search([])}
        currencies.update({x.symbol: x for x in Currency.search([])})

        def create_party(name, code):
            values = Party.default_get(
                    list(Party._fields.keys()), with_rec_name=False)
            party = Party(**values)
            party.name = name or code
            party.code = code
            if 'customer' in party._fields:
                party.customer = True
            party.save()
            return [party]

        sales_to_save = []
        lines_to_save = []
        previous_header = None
        for record in records:
            header = cls.import_sale_header(record)
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
                sale.sale_date = record.date

                if record.currency and record.currency in currencies.keys():
                    sale.currency = currencies.get(record.currency)

                party_domain=[]
                if record.party_name:
                    party_domain.append(('name', '=', record.party_name))
                if record.party_code:
                    party_domain.append(('code', '=', record.party_code))
                if party_domain and party_domain != []:
                    with Transaction().set_context(active_test=False):
                        parties = Party.search(party_domain)
                    if len(parties) != 1 and not force:
                        raise UserError(gettext('importer.single_party_error',
                                party=record.party_code))
                    elif not parties and force:
                        parties = create_party(record.party_name,
                            record.party_code)

                    party = parties[0]
                    sale.party = party
                    if force and 'customer' in Party._fields and not party.customer:
                        party.customer = True
                        party.save()
                    sale.on_change_party()
                else:
                    sale = None
                    continue
                sales_to_save.append(sale)

                if record.shipment_party_name:
                    parties = Party.search([
                            ('name', '=', record.shipment_party_name),
                            ])
                    if len(parties) != 1:
                        raise UserError(gettext('importer.single_party_error',
                                party=record.shipment_party_name))
                    sale.shipment_party = parties[0]
                    sale.on_change_shipment_party()

                if record.shipment_address:
                    addresses = Address.search([
                            ('rec_name', '=', record.shipment_address)
                            ], limit=1)
                    if addresses:
                        sale.shipment_address = addresses[0]

            if not sale or not sale.party:
                continue

            if record.product_code:
                product_domain = [('code', '=', record.product_code)]
                if not force:
                    product_domain += [('salable', '=', 'True')]
                with Transaction().set_context(active_test=False):
                    products = Product.search(product_domain)
                if len(products) != 1:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))

                product = products[0]
                template = product.template
                if force and not template.salable:
                    template.salable = True
                    template.save()
                if (force and 'validated' in Template._fields and
                        not template.validated):
                    template.validated = True
                    template.save()

                values = Line.default_get(
                    list(Line._fields.keys()), with_rec_name=False)
                line = Line(**values)
                line.sale = sale
                line.product = product
                line.on_change_product()
                line.quantity = record.quantity
                line.on_change_quantity()
                if 'product_package' in Line._fields:
                    line.product_package = None
                    line.package_quantity = None
                if ('gross_unit_price' in Line._fields
                            and record.unit_price is not None):
                    line.gross_unit_price = record.unit_price.quantize(exp)
                    line.discount = record.discount
                    line.update_prices()
                if ('manual_delivery_date' in Line._fields) and record.date:
                    line.manual_delivery_date = record.date
                elif record.unit_price is not None:
                    line.unit_price = record.unit_price.quantize(exp)
                lines_to_save.append(line)

        for to_save in grouped_slice(sales_to_save):
            Sale.save(list(to_save))

        for to_save in grouped_slice(lines_to_save):
            Line.save(list(to_save))

        #  print("quote:", len(sales_to_save), datetime.now() - start)
        #  if sales_to_save:
        #      sale.quote(sales_to_save)
        #  print("confirm:", len(sales_to_save), datetime.now() - start)
        #  if sales_to_save:
        #      Sale.confirm(sales_to_save)
        #  print("process:", len(sales_to_save), datetime.now() - start)
        #  if sales_to_save:
        #      Sale.process(sales_to_save)
        #  print("Sales:", len(sales_to_save), datetime.now() - start)
        return sales_to_save
