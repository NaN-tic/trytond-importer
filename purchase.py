from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterPurchase(ModelView):
    'Importer Purchase'
    __name__ = 'importer.purchase'

    reference = fields.Char('Reference')
    date = fields.Date('Date')
    party_name = fields.Char('Party Name')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'purchase': {
                    'string': 'Purchase',
                    'model': 'importer.purchase',
                    'chunked': False,
                    },
                })
        return methods

    @classmethod
    def import_purchase__header(cls, record):
        return (record.reference, record.date, record.party_name)

    @classmethod
    def import_purchase(cls, records):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        Line = pool.get('purchase.line')
        Party = pool.get('party.party')
        Product = pool.get('product.product')

        exp = Decimal(str(10.0 ** -Line.unit_price.digits[1]))

        purchases_to_save = []
        lines_to_save = []
        previous_header = None
        for record in records:
            header = cls.import_purchase_header(record)
            if any(header) and header != previous_header:
                previous_header = header
                values = Purchase.default_get(
                    list(Purchase._fields.keys()), with_rec_name=False)
                purchase = Purchase(**values)
                purchases_to_save.append(purchase)

                purchase.reference = record.reference
                purchase.purchase_date = record.date

                parties = Party.search([('name', '=', record.party_name)])
                if len(parties) != 1:
                    raise UserError(gettext('importer.single_party_error',
                            party=record.party_name))
                purchase.party = parties[0]
                purchase.on_change_party()

            if record.product_code:
                products = Product.search([
                        ('code', '=', record.product_code),
                        ('purchasable', '=', True),
                        ])
                if len(products) != 1:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))

                values = Line.default_get(
                    list(Line._fields.keys()), with_rec_name=False)
                line = Line(**values)
                line.purchase = purchase
                line.product = products[0]
                line.on_change_product()
                line.quantity = record.quantity
                line.on_change_quantity()
                if record.unit_price:
                    line.unit_price = record.unit_price.quantize(exp)
                lines_to_save.append(line)

        Purchase.save(purchases_to_save)
        Line.save(lines_to_save)
        return purchases_to_save
