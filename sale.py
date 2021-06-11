from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterSale(ModelView):
    'Importer Sale'
    __name__ = 'importer.sale'

    reference = fields.Char('Reference')
    date = fields.Date('Date')
    party_name = fields.Char('Party Name')
    shipment_party_name = fields.Char('Shipment Party Name')
    shipment_address = fields.Char('Shipment Address Name')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')


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
                })
        return methods

    @classmethod
    def import_sale_header(cls, record):
        return (record.reference, record.date, record.party_name,
            record.shipment_address)

    @classmethod
    def import_sale(cls, records):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        Address = pool.get('party.address')

        exp = Decimal(str(10.0 ** -Line.unit_price.digits[1]))

        sales_to_save = []
        lines_to_save = []
        previous_header = None
        for record in records:
            header = cls.import_sale_header(record)
            if any(header) and header != previous_header:
                previous_header = header
                values = Sale.default_get(                                  
                    list(Sale._fields.keys()), with_rec_name=False)        
                sale = Sale(**values)
                sales_to_save.append(sale)

                sale.reference = record.reference
                sale.sale_date = record.date

                if record.party_name:
                    parties = Party.search([('name', '=', record.party_name)])
                    if len(parties) != 1:
                        raise UserError(gettext('importer.single_party_error',
                                party=record.party_name))
                    sale.party = parties[0]
                    sale.on_change_party()

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

                
            if record.product_code:
                products = Product.search([
                        ('code', '=', record.product_code),
                        ('salable', '=', True),
                        ])
                if len(products) != 1:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))

                values = Line.default_get(
                    list(Line._fields.keys()), with_rec_name=False)        
                line = Line(**values)
                line.sale = sale
                line.product = products[0]
                line.on_change_product()
                line.quantity = record.quantity
                line.on_change_quantity()
                if record.unit_price:
                    line.unit_price = record.unit_price.quantize(exp)
                lines_to_save.append(line)

        Sale.save(sales_to_save)
        Line.save(lines_to_save)
        return sales_to_save
