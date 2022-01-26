from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from datetime import datetime

class ImporterPurchase(ModelView):
    'Importer Purchase'
    __name__ = 'importer.purchase'

    reference = fields.Char('Reference')
    date = fields.Date('Date')
    party_name = fields.Char('Party Name')
    party_code = fields.Char('Party Code')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')
    currency = fields.Char('Currency')
    invoice_method = fields.Char('Invoice Method')
    purchase_number = fields.Char('Purchase Number')
    discount = fields.Numeric('Discount')
    state = fields.Char('state')


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
    def import_purchase_header(cls, record):
        return (record.reference, record.date, record.party_name)

    @classmethod
    def import_purchase(cls, records):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        Line = pool.get('purchase.line')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        Currency = pool.get('currency.currency')

        exp = Decimal(str(10.0 ** -Line.unit_price.digits[1]))

        currencies = {x.name: x for x in Currency.search([])}
        currencies.update({x.symbol: x for x in Currency.search([])})

        start = datetime.now()
        purchases_to_save = []
        lines_to_save = []
        previous_header = None
        for record in records:
            header = cls.import_purchase_header(record)
            if any(header) and header != previous_header:
                previous_header = header
                values = Purchase.default_get(
                    list(Purchase._fields.keys()), with_rec_name=False)
                if record.invoice_method:
                    values['invoice_method'] = record.invoice_method

                purchases = []
                if record.purchase_number:
                    purchases = Purchase.search([
                        ('number', '=', record.purchase_number)], limit=1)

                purchase = Purchase(**values)
                if not purchases:
                    purchases_to_save.append(purchase)
                purchase.reference = record.reference
                purchase.purchase_date = record.date

                if record.state:
                    purchase.state = record.state
                if record.purchase_number:
                    purchase.number = record.purchase_number
                if record.currency and record.currency in currencies.keys():
                    purchase.currency = currencies.get(record.currency)

                party_domain=[]
                parties = []
                if record.party_name:
                    party_domain.append(('name', '=', record.party_name))
                if record.party_code:
                    party_domain.append(('code', '=', record.party_code))
                if party_domain and party_domain != []:
                    with Transaction().set_context(active_test=False):
                        parties = Party.search(party_domain)

                if len(parties) != 1:
                    raise UserError(gettext('importer.single_party_error',
                            party=record.party_code))

                purchase.party = parties[0]
                purchase.on_change_party()
                if record.invoice_method:
                    purchase.invoice_method = record.invoice_method

            if record.product_code:
                with Transaction().set_context(active_test=False):
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
                if ('gross_unit_price' in Line._fields
                        and record.unit_price is not None):
                    line.gross_unit_price = record.unit_price.quantize(exp)
                    line.discount = record.discount
                    line.update_prices()
                elif record.unit_price is not None:
                    line.unit_price = record.unit_price.quantize(exp)
                lines_to_save.append(line)

        for to_save in grouped_slice(purchases_to_save):
            Purchase.save(list(to_save))

        for to_save in grouped_slice(lines_to_save):
            Line.save(list(to_save))

        purchases = [x for x in purchases_to_save if x.state != 'done']
        print("quote:", len(purchases), datetime.now() - start)
        if purchases:
            Purchase.quote(purchases)
        print("confirm:", len(purchases), datetime.now() - start)
        if purchases:
            Purchase.confirm(purchases)
        print("process:", len(purchases), datetime.now() - start)
        if purchases:
            Purchase.process(purchases)
        print("Purchase:", len(purchases), datetime.now() - start)
        return purchases_to_save
