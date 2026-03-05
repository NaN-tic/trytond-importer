from datetime import datetime, timedelta
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.modules.product import round_price
from .tools import ImporterModel, Cache, Setup



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
    state = fields.Char('State')


class ImporterPurchaseConfiguration(ModelView):
    'Importer Purchase Configuration'
    __name__ = 'importer.purchase.configuration'

    company = fields.Char('Company')
    sequence_prefix = fields.Char("Purchase sequence prefix")
    sequence_suffix = fields.Char("Purchase sequence suffix")
    sequence_padding = fields.Integer("Purchase sequence padding")
    sequence_number_next = fields.Integer("Purchase sequence number next")
    invoice_method = fields.Char("Purchase invoice method")
    process_after = fields.Char("Purchase process after")


class ImporterProductSupplier(ImporterModel):
    'Importer Product Supplier'
    __name__ = 'importer.product.supplier'

    company = fields.Char('Company',
        help="Company field can be used to set company-dependent fields."
        "Better sort records by company prior to import for better "
        "performance.")
    template_code = fields.Char('Template Code')
    product_code = fields.Char('Product Code')
    party_name = fields.Char('Party Name')
    party_code = fields.Char('Party Code')
    currency = fields.Char('Currency')
    code = fields.Char('Code')
    quantity = fields.Float('Product Quantity')
    unit_price = fields.Numeric('Unit Price')
    lead_time = fields.Integer('Lead Time (days)')

    @classmethod
    def importer_start(cls):
        pool = Pool()
        ProductSupplier = pool.get('purchase.product_supplier')
        Price = pool.get('purchase.product_supplier.price')

        super().importer_start()
        cache = Setup.get().cache

        cache.currencies = Cache('currency.currency', ('name', 'symbol'))
        cache.companies = Cache('company.company',
            key=lambda x: x.party.name.lower())
        cache.parties_by_code = Cache('party.party', 'code',
            context={'active_test': False}, duplicates='abort-on-use')
        cache.parties_by_name = Cache('party.party', 'name',
            context={'active_test': False}, duplicates='abort-on-use')
        cache.products = Cache('product.product', 'code',
            context={'active_test': False}, duplicates='abort-on-use')
        cache.templates = Cache('product.template', 'code',
            context={'active_test': False}, duplicates='abort-on-use')
        cache.product_suppliers = Cache('purchase.product_supplier',
            lambda x: (x.party.id, x.template.id, x.product and x.product.id),
            context={'active_test': False}, required=False)
        cache.default_product_supplier_values = ProductSupplier.default_get(
            list(ProductSupplier._fields.keys()), with_rec_name=False)
        cache.default_price_values = Price.default_get(
            list(Price._fields.keys()), with_rec_name=False)

    def importer_context(self):
        res = super().importer_context()
        setup = Setup.get()
        if 'company' in setup.fields and self.company:
            company = setup.cache.companies.get(self.company)
            if company:
                res['company'] = company.id
        return res

    def importer_product_supplier(self, record):
        pass

    def importer_price(self, record):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ProductSupplier = pool.get('purchase.product_supplier')
        Price = pool.get('purchase.product_supplier.price')

        setup = Setup.get()
        cache = setup.cache

        lines_to_delete = {}
        lines_to_save = []
        product_supplier_to_save = {}
        templates_to_save = []
        for record in records:
            setup.current_record = record

            party = None
            if record.party_code:
                party = cache.parties_by_code.get(record.party_code)
            elif record.party_name:
                party = cache.parties_by_name.get(record.party_name)

            if not party:
                record.importer_error('Party not found')
                continue

            if record.product_code:
                product = cache.products.get(record.product_code)
                if not product:
                    continue
                template = product.template
            elif record.template_code:
                product = None
                template = cache.templates.get(record.template_code)
                if not template:
                    continue
            else:
                record.importer_error(
                    'importer.missing_template_product_code')
                continue

            key = (party.id, template.id, product and product.id)
            if key in product_supplier_to_save:
                product_supplier, _ = product_supplier_to_save[key]
            else:
                product_supplier = cache.product_suppliers.get(key)
                if product_supplier:
                    lines_to_delete[product_supplier] = {}
                    for price in product_supplier.prices:
                        lines_to_delete[product_supplier][price.quantity] = (
                            price)
                else:
                    product_supplier = ProductSupplier(**cache.default_product_supplier_values)

                    product_supplier.party = party
                    product_supplier.template = template
                    product_supplier.product = product
                    if 'company' in setup.fields and record.company:
                        product_supplier.company = cache.companies.get(record.company)
                        product_supplier.currency = product_supplier.company.currency
                    if not template.purchasable:
                        template.purchasable = True
                        template.purchase_uom = template.default_uom
                        templates_to_save.append((template, record))

            if 'currency' in setup.fields:
                product_supplier.currency = cache.currencies[record.currency]

            if 'lead_time' in setup.fields and record.lead_time is not None:
                product_supplier.lead_time = timedelta(
                    days=record.lead_time)

            record.importer_assign(product_supplier)

            record.importer_product_supplier(product_supplier)

            if record.unit_price:
                price = lines_to_delete.get(product_supplier, {}).get(
                        record.quantity)
                if price:
                    del lines_to_delete[product_supplier][record.quantity]
                else:
                    price = Price(**cache.default_price_values)
                    price.product_supplier = product_supplier

                price.quantity = record.quantity or 0
                price.unit_price = round_price(record.unit_price)

                if ('start_date' in setup.fields and record.start_date):
                    price.start_date = record.start_date
                if ('end_date' in setup.fields and record.end_date):
                    price.end_date = record.end_date

                record.importer_price(price)

                lines_to_save.append((price, record))

            product_supplier_to_save[key] = (product_supplier, record)

        setup.current_record = None
        to_delete = []
        for quantities in lines_to_delete.values():
            to_delete += quantities.values()
        Price.delete(to_delete)

        cls.importer_save(templates_to_save)
        to_save = list(product_supplier_to_save.values())
        cls.importer_save(to_save)
        cls.importer_save(lines_to_save)
        return [x[0] for x in to_save]


class ImporterProductSupplierStockSupplyMinimum(metaclass=PoolMeta):
    __name__ = 'importer.product.supplier'

    minimum_quantity = fields.Float('Minimum Quantity')


class ImporterProductSupplierStockSupplyMultiple(metaclass=PoolMeta):
    __name__ = 'importer.product.supplier'

    multiple_quantity = fields.Float('Multiple Quantity')


class ImporterProductSupplierPurchaseSupplierPricePeriod(metaclass=PoolMeta):
    __name__ = 'importer.product.supplier'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


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
                'purchase_configuration': {
                    'string': 'Purchase configuration',
                    'model': 'importer.purchase.configuration',
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

        currencies = {x.name: x for x in Currency.search([])}
        currencies.update({x.symbol: x for x in Currency.search([])})

        purchase = None
        purchases_to_save = []
        lines_to_save = []
        previous_header = None

        to_quote = []
        to_confirm = []
        to_process = []

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

                # purchase workflow (states)
                if record.state:
                    if record.state in ('draft', 'cancelled', 'done'):
                        purchase.state = record.state
                    elif record.state == 'quote':
                        to_quote += [purchase]
                    elif record.state == 'confirm':
                        to_confirm += [purchase]
                    elif record.state == 'process':
                        to_process += [purchase]

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

            if not purchase or not purchase.party:
                continue

            if record.product_code:
                with Transaction().set_context(active_test=False):
                    products = Product.search([
                        ('code', '=', record.product_code),
                        ('purchasable', '=', True),
                        ])
                if len(products) != 1:
                    active_products = []
                    for product in products:
                        if product.active:
                            active_products.append(product)
                    if len(active_products) == 1:
                        products = active_products
                    else:
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
                # TODO base_price
                if record.unit_price is not None:
                    line.unit_price = round_price(record.unit_price)
                lines_to_save.append(line)

        for to_save in grouped_slice(purchases_to_save):
            Purchase.save(list(to_save))

        for to_save in grouped_slice(lines_to_save):
            Line.save(list(to_save))

        to_confirm += to_process
        to_quote += to_confirm

        Purchase.quote(to_quote)
        Purchase.confirm(to_confirm)
        Purchase.process(to_process)

        return purchases_to_save

    @classmethod
    def import_purchase_configuration(cls, records):
        pool = Pool()

        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("purchase.configuration")
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
                configuration.purchase_invoice_method = record.invoice_method
                configuration.purchase_process_after = record.process_after

                if record.sequence_padding or record.sequence_number_next:
                    sequence = configuration.purchase_sequence

                    if not sequence or (sequence.company and sequence.company.id != company_id):
                        sequence = Sequence()
                        sequence.name = "Purchase"
                        configuration.purchase_sequence = sequence
                    sequence.company = company_id
                    sequence.sequence_type = ModelData.get_id('purchase', 'sequence_type_purchase')
                    sequence.prefix = record.sequence_prefix
                    sequence.suffix = record.sequence_suffix
                    sequence.padding = record.sequence_padding
                    sequence.number_next = record.sequence_number_next
                    sequence.save()

                configuration.save()
                configs.append(configuration)

        return configs
