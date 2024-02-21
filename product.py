from itertools import groupby
from decimal import Decimal
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import ModelView, fields
from trytond.modules.product import price_digits, round_price
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class ImporterProduct(ModelView):
    'Importer Product'
    __name__ = 'importer.product'

    company = fields.Char('Company',
        help="Company field can be used to set company-dependent fields."
        "Better sort records by company prior to import for better "
        "performance.")
    template_code = fields.Char('Template Code')
    variant_code = fields.Char('Variant Code')
    variant_suffix_code = fields.Char('Variant Suffix Code')
    name = fields.Char('Name')
    description = fields.Char('Description')
    uom = fields.Char('UoM')
    sale_price = fields.Numeric('Sale Price', digits=price_digits)
    cost_price = fields.Numeric('Cost Price', digits=price_digits)
    type_ = fields.Char('Type')
    cost_price_method = fields.Char('Cost Price Method')
    supplier = fields.Char('Supplier')
    supplier_code = fields.Char('Supplier Code')
    supplier_currency = fields.Char('Supplier Currency')
    supplier_unit_price = fields.Numeric('Supplier Unit Price',
        digits=price_digits)
    categories = fields.Char('Categories')
    account_category = fields.Char('Account Category')
    aranzel = fields.Char('Aranzel')
    consumable =  fields.Boolean('Consumable')
    purchasable = fields.Boolean('Purchasable')
    salable = fields.Boolean('Salable')
    brand = fields.Char('Brand')
    template_note = fields.Text('Template Note')
    product_note = fields.Text('Product Note')

class ImporterProductConfiguration(ModelView):
    'Importer Product Configuration'
    __name__ = "importer.product.configuration"

    cost_price_method = fields.Char("Cost price method")
    template_sequence_prefix = fields.Char("Sequence prefix")
    template_sequence_suffix = fields.Char("Sequence suffix")
    template_sequence_padding = fields.Integer("Sequence padding")
    template_sequence_number_next = fields.Integer("Sequence number next")


class ImporterProductProductionDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    producible = fields.Boolean('Producible')
    bom_name = fields.Char('BOM Name')


class ImporterProductProductionRouteDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    bom_route = fields.Char('BOM Route')


class ImporterProductProductMeasuresDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    width = fields.Float('Width')
    width_uom = fields.Char('Width Uom')
    length = fields.Float('Length')
    length_uom = fields.Char('Length Uom')
    height = fields.Float('Height')
    height_uom = fields.Char('Height Uom')
    weight = fields.Float('Weight')
    weight_uom = fields.Char('Weight Uom')
    volume = fields.Float('Volume')
    volume_uom = fields.Char('Volume Uom')


class ImporterProductPackagesDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    packages = fields.Boolean('Packages')


class ImporterProductSupplierMinimumDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    supplier_minimum_quantity = fields.Float('Supplier Minimum Quantity')


class ImporterProductSupplierMultipleDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    supplier_multiple_quantity = fields.Float('Supplier Multiple Quantity')


class ImporterProductCodes(ModelView):
    'Importer Product'
    __name__ = 'importer.product_codes'

    template_code = fields.Char('Template Code')
    variant_code = fields.Char('Variant Code')
    variant_suffix_code = fields.Char('Variant Suffix Code')
    type_ = fields.Char('type')
    code = fields.Char('Code')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'product': {
                    'string': 'Product',
                    'model': 'importer.product',
                    'chunked': True,
                    },
                'product_codes': {
                    'string': 'Product Codes',
                    'model': 'importer.product_codes',
                    'chunked': True,
                    },
                'product_configuration': {
                    'string': 'Product configuration',
                    'model': 'importer.product.configuration',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_product_codes(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Identifier = pool.get('product.identifier')

        products = dict((x.code, x) for x in Product.search([
                    ('code', '!=', None),
                    ('code', '!=', ''),
                    ]))
        to_save = []
        for record in records:
            if not record.code:
                continue
            identifier = Identifier()
            identifier.type = record.type_
            if record.variant_code:
                code = record.variant_code
            else:
                code = ((record.template_code or '')
                    + (record.variant_suffix_code or ''))
            identifier.code = record.code
            product = products.get(code)
            if not product:
                # TODO: Raise an error
                continue
            identifier.product = product
            to_save.append(identifier)

        Identifier.save(to_save)
        return to_save

    @classmethod
    def _import_template_hook(cls, record, template):
        pass

    @classmethod
    def _import_product_hook(cls, record, product):
        pass

    @classmethod
    def import_product(cls, records):
        pool = Pool()
        try:
            Company = pool.get('company.company')
        except KeyError:
            Company = None

        imported = []
        for company_name, records in groupby(records, key=lambda x: x.company):
            company_id = Transaction().context.get('company')
            if Company:
                if company_name:
                    companies = Company.search([('party.name', '=', company_name)], limit=1)
                    if not companies:
                        raise UserError(gettext('importer.msg_company_not_found',
                            company=company_name))
                    company_id = companies[0].id
                elif not company_id:
                    companies = Company.search([], limit=1)
                    if companies:
                        company, = companies
            with Transaction().set_context(company=company_id):
                imported += cls._import_product(records)
        return imported

    @classmethod
    def _import_product(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        ProductCategory = pool.get('product.category')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        ProductCostPriceMethod = pool.get('product.cost_price_method')
        Note = pool.get('ir.note')

        try:
            ProductSupplier = pool.get('purchase.product_supplier')
            ProductSupplierPrice = pool.get('purchase.product_supplier.price')
            Party = pool.get('party.party')
            parties = dict((x.code, x) for x in Party.search([]))
        except:
            parties = {}

        try:
            TariffCodeRel = pool.get('product-customs.tariff.code')
            TariffCode = pool.get('customs.tariff.code')
            customs = dict((x.code, x) for x in TariffCode.search([]))
        except:
            customs = {}

        try:
            Brand = pool.get('product.brand')
            brands = dict((x.name, x) for x in Brand.search([]))
        except:
            brands = {}

        try:
            BOM = pool.get('production.bom')
            boms = dict([(x.name, x) for x in BOM.search([])])
            ProductBom = pool.get('product.product-production.bom')
        except:
            ProductBom = None

        try:
            ProductionRoute = pool.get('production.route')
        except:
            ProductionRoute = None

        try:
            Package = pool.get('product.package')
        except KeyError:
            pass

        try:
            Currency = pool.get('currency.currency')
            currencies = {x.name: x for x in Currency.search([])}
            currencies.update({x.symbol: x for x in Currency.search([])})
        except KeyError:
            currencies = {}

        categories = dict((x.name, x) for x in ProductCategory.search([]))
        uoms = {}
        for uom in Uom.search([]):
            uoms[uom.name.lower()] = uom
            uoms[uom.symbol.lower()] = uom

        products = dict((x.code, x) for x in Product.search([
                    ('code', '!=', None),
                    ('code', '!=', ''),
                    ]))
        templates = dict((x.code, x) for x in Template.search([
                    ('code', '!=', None),
                    ('code', '!=', ''),
                    ]))

        if ProductionRoute:
            bom_routes = dict((x.name, x) for x in ProductionRoute.search([]))

        template_default_values = Template.default_get(Template._fields.keys(),
                with_rec_name=False)
        product_default_values = Product.default_get(Product._fields.keys(),
                with_rec_name=False)
        cost_price_methods = ProductCostPriceMethod.get_cost_price_methods()

        to_save = []
        products_to_save = []
        notes_to_save = []
        for record in records:
            product = None
            template = None
            if record.variant_code:
                code = record.variant_code
            else:
                code = ((record.template_code or '')
                    + (record.variant_suffix_code or ''))
            product = products.get(code)
            if product:
                template = product.template
            elif record.template_code in templates:
                template = templates.get(record.template_code)

            if not template:
                template = Template(**template_default_values)
                template.products = []

            if not product:
                product = Product(**product_default_values)
                template.products += (product,)
            else:
                products_to_save.append(product)
            to_save.append(template)

            if record.name:
                template.name = record.name
            if record.template_code:
                template.code = record.template_code
            if record.sale_price:
                template.list_price = record.sale_price or Decimal(0)
            uom = None
            if record.uom:
                uom = uoms.get(record.uom.lower(), 'u')
            else:
                uom = uoms.get('u')
                # If we update a product, we dont need to change the uom
                if hasattr(product, 'default_uom') and product.default_uom:
                    uom = None

            if uom:
                template.default_uom = uom
            if record.cost_price_method:
                cost_price_method = record.cost_price_method
                for cpm in cost_price_methods:
                    if cpm[1] == record.cost_price_method:
                        cost_price_method = cpm[0]

                template.cost_price_method = cost_price_method

            if ('account_category' in template._fields and
                    record.account_category):
                acc_category = categories.get(record.account_category)
                if not acc_category:
                    acc_category = ProductCategory()
                    acc_category.name = record.account_category
                    categories[record.account_category] = acc_category
                acc_category.accounting = True
                template.account_category = acc_category

            measures = template
            if hasattr(Product, 'weight'):
                measures = product

            if 'weight' in measures._fields and record.weight:
                measures.weight = record.weight
                measures.weight_uom = (uoms.get(record.weight_uom) or
                    uoms.get('kg'))

            if 'volume' in measures._fields and record.volume:
                measures.volume = record.volume
                measures.volume_uom = (uoms.get(record.volume_uom) or
                    uoms.get('l'))

            if 'width' in measures._fields and record.width is not None:
                measures.width = record.width
                measures.width_uom = (uoms.get(record.width_uom) or
                    uoms.get('m'))

            if 'length' in measures._fields and record.length:
                measures.length = record.length
                measures.length_uom = (uoms.get(record.length_uom) or
                    uoms.get('m'))

            if 'height' in measures._fields and record.height:
                measures.height = record.height
                measures.height_uom = (uoms.get(record.height_uom) or
                    uoms.get('m'))

            if 'tariff_codes' in template._fields and record.aranzel:
                custom = customs.get(record.aranzel)
                if not custom:
                    custom = TariffCode()
                    custom.code = record.aranzel
                    customs[record.aranzel] = custom

                rel = TariffCodeRel()
                rel.tariff_code = custom
                template.tariff_codes = [rel]

            # If product exist the categories are set all new, not updated.
            if record.categories:
                cats = []
                for cat in record.categories.split('|'):
                    category = categories.get(cat)
                    if not category and cat:
                        category = ProductCategory()
                        category.name = cat
                    if category:
                        cats += [category]
                        categories[cat] = category
                template.categories = cats

            template.consumable = record.consumable

            if hasattr(Template, 'producible'):
                template.producible = record.producible
                bom = boms.get(record.bom_name)
                if bom:
                    if ProductBom:
                        product_bom = ProductBom()
                        product_bom.bom = bom
                        if 'route' in ProductBom._fields and record.bom_route:
                            bom_route = bom_routes.get(record.bom_route)
                            if bom_route:
                                product_bom.route = bom_route
                    if hasattr(product, 'boms'):
                        product.boms += (product_bom,)
                    else:
                        product.boms = [product_bom]

            if 'purchasable' in template._fields and record.purchasable:
                template.purchasable = record.purchasable
                template.purchase_uom = template.default_uom

            if 'salable' in template._fields and record.salable:
                template.salable = record.salable
                template.sale_uom = template.default_uom

            if parties and record.supplier:
                party = parties.get(record.supplier)
                supplier = ProductSupplier()
                supplier.party = party
                supplier.code = record.supplier_code
                if record.supplier_currency:
                    supplier.currency = currencies.get('supplier_currency')
                if ProductSupplier._fields.get('minimum_quantity') and record.supplier_minimum_quantity:
                    supplier.minimum_quantity = record.minimum_quantity
                if ProductSupplier._fields.get('multiple_quantity') and record.supplier_multiple_quantity:
                    supplier.multiple_quantity = record.multiple_quantity
                if record.supplier_unit_price:
                    supplier_price = ProductSupplierPrice()
                    supplier_price.quantity = 0
                    supplier_price.unit_price = round_price(record.supplier_unit_price)
                    supplier.prices.append(supplier_price)
                template.product_suppliers = [supplier]
                templates[record.template_code] = template

                if 'brand' in template._fields and record.brand:
                    brand = brands.get(record.brand)
                    if not brand:
                        brand = Brand()
                        brand.name = record.brand
                        brands[record.brand] = brand
                        template.brand = brand

            if record.variant_suffix_code:
                product.suffix_code = record.variant_suffix_code
            if record.sale_price:
                product.list_price = record.sale_price or Decimal(0)
            if record.cost_price:
                product.cost_price = record.cost_price or Decimal(0)
            if record.description:
                product.description = record.description

            # If product exist the packages are set all new, not updated.
            if 'packages' in template._fields and record.packages:
                packages = []
                for package in record.packages.split('|'):
                    name, quantity, is_default = package.split(';')
                    ppackage = Package()
                    ppackage.name = name
                    ppackage.quantity = quantity
                    ppackage.is_default = True if is_default == '1' else False
                    packages.append(ppackage)
                template.packages = packages

            if record.template_note:
                note = Note()
                note.resource = template
                note.message = record.template_note
                notes_to_save.append(note)
            if record.product_note:
                note = Note()
                note.resource = product
                note.message = record.product_note
                notes_to_save.append(note)
            cls._import_template_hook(record, template)
            cls._import_product_hook(record, product)
            template.save()
            templates[record.template_code] = template

        ProductCategory.save(categories.values())
        Template.save(to_save)
        Product.save(products_to_save)
        Note.save(notes_to_save)
        return to_save

    @classmethod
    def import_product_configuration(cls, records):
        pool = Pool()

        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("product.configuration")
        ModelData = pool.get("ir.model.data")

        configs = []
        for record in records:
            configuration = Configuration(1)
            configuration.default_cost_price_method = record.cost_price_method

            if record.template_sequence_padding or record.template_sequence_number_next:
                sequence = configuration.product_sequence

                if not sequence:
                    sequence = Sequence()
                    sequence.name = "Product"
                    configuration.product_sequence = sequence

                sequence.sequence_type = ModelData.get_id('product', 'sequence_type_product')
                sequence.prefix = record.template_sequence_prefix
                sequence.suffix = record.template_sequence_suffix
                sequence.padding = record.template_sequence_padding
                sequence.number_next = record.template_sequence_number_next
                sequence.save()

            configuration.save()
            configs.append(configuration)

        return configs
