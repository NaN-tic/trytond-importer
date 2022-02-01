from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.tools import grouped_slice
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
                'invoice_force': {
                    'string': 'Invoice Create/Fix Party and Products',
                    'model': 'importer.invoice',
                    'chunked': False,
                    },
                })
        return methods

    @classmethod
    def import_invoice_header(cls, record):
        return (record.invoice_number, record.journal)

    @classmethod
    def import_invoice_force(cls, records):
        return cls.import_invoice(records, force=True)

    @classmethod
    def import_invoice(cls, records, force=False):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.invoice.line')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        Journal = pool.get('account.journal')
        Currency = pool.get('currency.currency')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        currencies = {x.name: x for x in Currency.search([])}
        currencies.update({x.symbol: x for x in Currency.search([])})
        with Transaction().set_context(active_test=False):
            products = dict((x.code, x) for x in Product.search([]))
        journals = dict((x.code, x) for x in Journal.search([]))
        invoices_to_save = []
        invoices_to_post = []
        lines_to_save = []
        previous_header = None
        invoice = None
        start = datetime.now()
        company = Transaction().context.get('company')
        moves = dict(((x.post_number, x.period), x)
            for x in Move.search([('company', '=', company)]))
        invoices = dict(((x.number, x.journal.name), x) for x in
            Invoice.search([('company', '=', company)]))
        
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

        for record in records:
            header = cls.import_invoice_header(record)
            if any(header) and header != previous_header:
                previous_header = header
                values = Invoice.default_get(
                    list(Invoice._fields.keys()), with_rec_name=False)
                if invoice:
                    invoice.on_change_lines()

                invoice = invoices.get((record.invoice_number, record.journal))
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
                    with Transaction().set_context(active_test=False):
                        parties = Party.search([('name', '=', record.party_name)])
                    if len(parties) != 1:
                        raise UserError(gettext('importer.single_party_error',
                                party=record.party_name))
                    invoice.party = parties[0]
                elif record.party_code:
                    with Transaction().set_context(active_test=False):
                        parties = Party.search(
                            [('code', '=', record.party_code)])
                    if len(parties) != 1 and not force:
                        raise UserError(gettext('importer.single_party_error',
                                party=record.party_code))
                    elif not parties and force:
                        parties = create_party(record.party_name or
                            record.party_code, record.party_code)
                    party = parties[0]

                if (force and 'customer' in Party._fields and 
                        not party.customer):
                    party.customer = True
                    party.save()

                invoice.party = party
                invoice.on_change_type()
                invoice.on_change_party()
                invoice.account = invoice.on_change_with_account()
                invoice.journal = journals.get(record.journal)

                if record.account_move_number:
                    period = Period.search([
                            ('start_date', '<=', record.invoice_date),
                            ('end_date', '>=', record.invoice_date),
                            ('type', '=', 'standard'),
                            ('company', '=', company),
                            ], limit=1)
                    move = moves.get((record.account_move_number, period[0]))
                    if move:
                        print(move, invoice)
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
                if (force and invoice.type == 'invoice_out'):
                    if not product.salable:
                        product.active = True
                        product.salable = True
                        product.save()
                    if ('validated' in Template._fields and
                            not product.template.validated):
                        template = product.template
                        template.active = True
                        template.validated = True
                        template.save()
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

        for to_save in grouped_slice(invoices_to_save):
            Invoice.save(list(to_save))

        for to_save in grouped_slice(lines_to_save):
            Line.save(list(to_save))

        print("Invoices:", len(invoices_to_save), datetime.now() - start)
        Invoice.post_batch(invoices_to_post)
        print("Invoices:" , len(invoices_to_save), datetime.now() - start)
        return invoices_to_save
