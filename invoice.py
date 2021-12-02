from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.transaction import Transaction
from datetime import datetime

class ImporterInvoice(ModelView):
    'Importer Invoice'
    __name__ = 'importer.invoice'

    invoice_number = fields.Char('Invoice Number')
    reference = fields.Char('Reference')
    invoice_date = fields.Date('Date')
    party_name = fields.Char('Party Name')
    party_code = fields.Char('Party Code')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')
    discount = fields.Numeric('Discount')
    currency = fields.Char('Currency')
    invoice_type = fields.Char('Invoice Type')
    journal = fields.Char('Journal')
    account_move_number = fields.Char('Account Move number')

class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'invoice': {
                    'string': 'Invoice',
                    'model': 'importer.invoice',
                    'chunked': False,
                    },
                })
        return methods

    @classmethod
    def import_invoice_header(cls, record):
        return (record.invoice_number, record.journal)

    @classmethod
    def import_invoice(cls, records):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.invoice.line')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        Journal = pool.get('account.journal')
        Currency = pool.get('currency.currency')
        Move = pool.get('account.move')

        exp = Decimal(str(10.0 ** -Line.unit_price.digits[1]))
        currencies = {x.name: x for x in Currency.search([])}
        currencies.update({x.symbol: x for x in Currency.search([])})
        clients = cls.get_party_dict()
        products = dict((x.code, x) for x in Product.search([]))
        journals = dict((x.name, x) for x in Journal.search([]))
        invoices_to_save = []
        invoices_to_post = []
        lines_to_save = []
        moves_to_save = []
        previous_header = None
        invoice = None
        start = datetime.now()

        for record in records:
            header = cls.import_invoice_header(record)
            if any(header) and header != previous_header:
                previous_header = header
                values = Invoice.default_get(
                    list(Invoice._fields.keys()), with_rec_name=False)
                if invoice:
                    invoice.on_change_lines()

                invoice = Invoice.search([
                    ('number', '=', record.invoice_number),
                    ('journal.name', '=', record.journal)], limit=1)

                if invoice:
                    invoice = None
                    continue

                invoice = Invoice(**values)
                invoices_to_save.append(invoice)

                invoice.reference = record.reference
                invoice.number = record.invoice_number
                invoice.invoice_date = record.invoice_date
                invoice.type = record.invoice_type

                if record.currency and record.currency in currencies.keys():
                    invoice.currency = currencies.get(record.currency)

                if record.party_name:
                    parties = Party.search([('name', '=', record.party_name)])
                    if len(parties) != 1:
                        raise UserError(gettext('importer.single_party_error',
                                party=record.party_name))
                    invoice.party = parties[0]
                elif record.party_code:
                    parties = Party.search(
                        [('code', '=', record.party_code)])
                    party = parties[0]

                invoice.party = party
                invoice.on_change_type()#
                invoice.on_change_party()
                invoice.account = invoice.on_change_with_account()
                invoice.journal = journals.get(record.journal)

                if record.account_move_number:
                    moves = Move.search([('post_number', '=',
                        record.account_move_number)], limit=1)
                    if moves:
                        move, = moves
                        invoice.move = move
                        invoices_to_post.append(invoice)

            if not invoice:
                continue

            if record.product_code:
                product = products.get(record.product_code)
                if not product:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))

                values = Line.default_get(
                    list(Line._fields.keys()), with_rec_name=False)
                line = Line(**values)
                line.invoice = invoice
                line.product = product
                line.on_change_product()
                line.account.company.party.name
                if 'gross_unit_price' in Line._fields:
                    line.gross_unit_price = record.unit_price
                    line.discount = record.discount
                    line.update_prices()
                elif record.unit_price is not None:
                    line.unit_price = record.unit_price
                line.quantity = record.quantity
                line.on_change_quantity()
                line.on_change_account()
                lines_to_save.append(line)

        offset = 500
        i = 0
        while i <= len(invoices_to_save):
            m = invoices_to_save[i:min(i+offset, len(lines_to_save))]
            i += offset
            Invoice.save(m)

        i = 0
        while i <= len(lines_to_save):
            m = lines_to_save[i:min(i+offset, len(lines_to_save))]
            i += offset
            Line.save(m)

        Invoice.post_batch(invoices_to_post)
        print("Invoices:" , len(invoices_to_save), datetime.now() - start)
        return invoices_to_save
