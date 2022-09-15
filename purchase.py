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

class ImporterProductSupplier(ModelView):
    'Importer Product Supplier'
    __name__ = 'importer.product.supplier'

    template_code = fields.Char('Template Code')
    product_code = fields.Char('Product Code')
    party_name = fields.Char('Party Name')
    party_code = fields.Char('Party Code')
    currency = fields.Char('Currency')
    code = fields.Char('Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')
    lead_time = fields.TimeDelta('Lead Time')


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
                'purchase_force': {
                    'string': 'Purchase Force',
                    'model': 'importer.purchase',
                    'chunked': False,
                    },
                'purchase_product_supplier': {
                    'string': 'Purchase Product Supplier',
                    'model': 'importer.product.supplier',
                    'chunked': False,
                    },
                })
        return methods

    @classmethod
    def import_purchase_header(cls, record):
        return (record.reference, record.date, record.party_name)

    @classmethod
    def import_purchase_force(cls, records):
        return cls.import_purchase(records, force=True)

    @classmethod
    def import_purchase(cls, records, force=False):
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
                    domain = [('number', '=', record.purchase_number)]
                    if record.date:
                        domain += [('purchase_date', '=', record.date)]
                    purchases = Purchase.search(domain, limit=1)

                purchase = Purchase(**values)
                if not purchases:
                    purchases_to_save.append(purchase)
                purchase.reference = record.reference
                purchase_date = record.date
                if isinstance(record.date, datetime):
                    purchase_date = record.date.date()
                purchase.purchase_date = purchase_date

                if record.state:
                    purchase.state = record.state
                if record.purchase_number:
                    purchase.number = record.purchase_number

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

                if record.currency and record.currency in currencies.keys():
                    purchase.currency = currencies.get(record.currency)

                if record.invoice_method:
                    purchase.invoice_method = record.invoice_method

            if record.product_code:
                with Transaction().set_context(active_test=False):
                    products = Product.search([
                        ('code', '=', record.product_code),
                        ])
                if len(products) != 1:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))

                values = Line.default_get(
                    list(Line._fields.keys()), with_rec_name=False)
                line = Line(**values)
                product = products[0]
                template = product.template
                if force and not template.purchasable:
                    template.purchasable = True
                    template.save()

                line.purchase = purchase
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
                elif record.unit_price is not None:
                    line.unit_price = record.unit_price.quantize(exp)
                lines_to_save.append(line)

        for to_save in grouped_slice(purchases_to_save):
            Purchase.save(list(to_save))

        for to_save in grouped_slice(lines_to_save):
            Line.save(list(to_save))

        purchases = [x for x in purchases_to_save if x.state != 'done']
        if purchases:
            Purchase.quote(purchases)
        if purchases:
            Purchase.confirm(purchases)
        if purchases:
            Purchase.process(purchases)
        return purchases_to_save

    @classmethod
    def import_purchase_product_supplier(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        ProductSupplier = pool.get('purchase.product_supplier')
        Price = pool.get('purchase.product_supplier.price')
        Product = pool.get('product.product')
        Currency = pool.get('currency.currency')
        Template = pool.get('product.template')

        currencies = {x.name: x for x in Currency.search([])}
        currencies.update({x.symbol: x for x in Currency.search([])})

        lines_to_delete = {}
        lines_to_save = []
        product_supplier_to_save = {}
        for record in records:
            party_domain=[]
            parties = []
            if record.party_code:
                party_domain.append(('code', '=', record.party_code))
            elif record.party_name:
                party_domain.append(('name', '=', record.party_name))
            if party_domain and party_domain != []:
                with Transaction().set_context(active_test=False):
                    parties = Party.search(party_domain)
            if len(parties) != 1:
                raise UserError(gettext('importer.single_party_error',
                        party=(record.party_code or record.party_name)))
            party, = parties

            if record.product_code:
                with Transaction().set_context(active_test=False):
                    products = Product.search([
                        ('code', '=', record.product_code),
                        ])
                if len(products) != 1:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))
                product, = products
                template = product.template
            elif record.template_code:
                with Transaction().set_context(active_test=False):
                    templates = Template.search([
                        ('code', '=', record.template_code),
                        ])
                if len(templates) != 1:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.template_code))
                product = None
                template, = templates
            else:
                raise UserError(gettext(
                    'importer.missing_template_product_code'))

            key = (party.id, template.id, product.id)
            if key in product_supplier_to_save:
                product_supplier = product_supplier_to_save[key]
            else:
                product_suppliers = ProductSupplier.search([
                    ('party', '=', party.id),
                    ('template', '=', template.id),
                    ('product', '=', product.id),
                    ])
                if len(product_suppliers) == 1:
                    product_supplier, = product_suppliers
                    lines_to_delete = {}
                    lines_to_delete[product_supplier] = {}
                    for price in product_supplier.prices:
                        lines_to_delete[product_supplier][price.quantity] = (
                            price)
                else:
                    values = ProductSupplier.default_get(
                    list(ProductSupplier._fields.keys()), with_rec_name=False)
                    product_supplier = ProductSupplier(**values)

                    product_supplier.party = party
                    product_supplier.template = template
                    product_supplier.product = product
                    if not template.purchasable:
                        template.purchasable = True
                        template.purchase_uom = template.default_uom
                        template.save()
            if record.code:
                product_supplier.code = record.code
            if record.currency and record.currency in currencies.keys():
                product_supplier.currency = currencies.get(record.currency)
            if record.lead_time:
                product_supplier.lead_time = record.lead_time

            if record.unit_price:
                price = lines_to_delete.get(product_supplier, {}).get(
                        record.quantity)
                if price:
                    del lines_to_delete[product_supplier][record.quantity]
                else:
                    values = Price.default_get(
                        list(Price._fields.keys()), with_rec_name=False)
                    price = Price(**values)
                    if product_supplier.id is None:
                        product_supplier.save()
                    price.product_supplier = product_supplier
                price.quantity = record.quantity
                price.unit_price = record.unit_price
                lines_to_save.append(price)

            product_supplier_to_save[key] = product_supplier

        to_save = list(product_supplier_to_save.values())
        ProductSupplier.save(to_save)

        Price.save(lines_to_save)
        to_delete = []
        for quantities in lines_to_delete.values():
            to_delete += quantities.values()
        Price.delete(to_delete)
        return to_save
