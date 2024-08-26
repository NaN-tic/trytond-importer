from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.modules.product import price_digits, round_price
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel, Cache, Setup


class ImporterProduct(ImporterModel):
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
    location = fields.Char('Location')

    @classmethod
    def importer_template(self, template):
        pass

    @classmethod
    def importer_product(self, product):
        pass

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.companies = Cache('company.company', key=lambda x: x.party.name)
        cache.parties = Cache('party.party', 'code', context={'active_test': False},
            duplicates='abort-on-use')
        cache.customs = Cache('customs.tariff.code', 'code')
        cache.brands = Cache('product.brand', 'name')
        cache.boms = Cache('production.bom', 'name')
        cache.currencies = Cache('currency.currency', ('name', 'symbol'))
        cache.uoms = Cache('product.uom', ('name', 'symbol'))
        cache.categories = Cache('product.category', 'name')
        cache.bom_routes = Cache('production.route', 'name')
        cache.products = Cache('product.product', 'code', domain=[
                ('code', '!=', None),
                ('code', '!=', ''),
                ], required=False)
        cache.templates = Cache('product.template', 'code', domain=[
                ('code', '!=', None),
                ('code', '!=', ''),
                ], required=False)
        cache.accounts = Cache('account.account', 'code')

    def importer_context(self):
        res = super().importer_context()
        setup = Setup.get()
        if 'company' in setup.fields and self.company:
            company = setup.cache.companies.get(self.company)
            if company:
                res['company'] = company.id
        return res

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        ProductCategory = pool.get('product.category')
        Template = pool.get('product.template')
        ProductCostPriceMethod = pool.get('product.cost_price_method')
        Note = pool.get('ir.note')

        def object_to_set(template, product, field):
            field = getattr(Product, field, None)
            if isinstance(field, fields.Function) and not field.setter:
                return template
            return product

        setup = Setup.get()
        cache = setup.cache
        try:
            ProductSupplier = pool.get('purchase.product_supplier')
            ProductSupplierPrice = pool.get('purchase.product_supplier.price')
        except:
            pass
        try:
            TariffCodeRel = pool.get('product-customs.tariff.code')
            TariffCode = pool.get('customs.tariff.code')
        except:
            pass

        try:
            Brand = pool.get('product.brand')
        except:
            pass

        try:
            ProductBom = pool.get('product.product-production.bom')
        except:
            ProductBom = None

        try:
            Package = pool.get('product.package')
        except KeyError:
            pass

        template_default_values = Template.default_get(Template._fields.keys(),
                with_rec_name=False)
        product_default_values = Product.default_get(Product._fields.keys(),
                with_rec_name=False)
        cost_price_methods = ProductCostPriceMethod.get_cost_price_methods()

        to_save = []
        products_to_save = []
        notes_to_save = []
        categories_to_save = []

        for record in records:
            product = None
            template = None
            if 'variant_code' in setup.fields and record.variant_code:
                code = record.variant_code
            else:
                code = ((record.template_code or '')
                    + (record.variant_suffix_code or ''))
            product = cache.products.get(code)
            if product:
                template = product.template

            if record.template_code and record.template_code in cache.templates:
                template = cache.templates.get(record.template_code)
                if not template and product:
                    template = product.template

            if not template:
                template = Template(**template_default_values)
                template.products = []

            if not product:
                product = Product(**product_default_values)
                template.products += (product,)
            else:
                products_to_save.append(product)
            to_save.append(template)

            if 'name' in setup.fields:
                template.name = record.name
            if 'template_code' in setup.fields:
                template.code = record.template_code
            if 'sale_price' in setup.fields:
                template.list_price = record.sale_price or Decimal(0)
            uom = None
            if record.uom:
                uom = cache.uoms.get(record.uom.lower(), 'u')
            else:
                uom = cache.uoms.get('u')
                # If we update a product, we dont need to change the uom
                if product.id is not None:
                    uom = None

            if uom:
                template.default_uom = uom
            if record.cost_price_method:
                cost_price_method = record.cost_price_method
                for cpm in cost_price_methods:
                    if cpm[1] == record.cost_price_method:
                        cost_price_method = cpm[0]

                template.cost_price_method = cost_price_method

            if ('account_category' in setup.fields and
                    record.account_category):
                acc_category = cache.categories.get(record.account_category)
                if not acc_category:
                    acc_category = ProductCategory()
                    acc_category.name = record.account_category
                    cache.categories[record.account_category] = acc_category
                    categories_to_save.append(acc_category)
                acc_category.accounting = True
                template.account_category = acc_category

            for field in ('weight', 'volume', 'width', 'length', 'height'):
                if field not in setup.fields:
                    continue
                obj = object_to_set(template, product, field)
                setattr(obj, field, getattr(record, field))

            for field in ('weight_uom', 'volume_uom', 'width_uom',
                    'length_uom', 'height_uom'):
                if field not in setup.fields:
                    continue
                obj = object_to_set(template, product, field)
                uom = cache.uoms.get(getattr(record, field))
                setattr(obj, field, uom)

            if 'tariff_codes' in setup.fields and record.aranzel:
                custom = cache.customs.get(record.aranzel)
                if not custom:
                    custom = TariffCode()
                    custom.code = record.aranzel
                    cache.customs[record.aranzel] = custom

                rel = TariffCodeRel()
                rel.tariff_code = custom
                template.tariff_codes = [rel]

            # If product exist the categories are set all new, not updated.
            if 'categories' in setup.fields and record.categories:
                cats = []
                for cat in record.categories.split('|'):
                    category = cache.categories.get(cat)
                    if not category and cat:
                        category = ProductCategory()
                        category.name = cat
                        cache.categories[cat] = category
                        category.save()
                    if category:
                        cats += [category]
                        cache.categories[cat] = category
                template.categories = cats

            if 'consumable' in setup.fields:
                template.consumable = record.consumable

            if 'producible' in setup.fields:
                template.producible = record.producible
                bom = cache.boms.get(record.bom_name)
                if bom:
                    if ProductBom:
                        product_bom = ProductBom()
                        product_bom.bom = bom
                        if 'route' in ProductBom._fields and record.bom_route:
                            bom_route = cache.bom_routes.get(record.bom_route)
                            if bom_route:
                                product_bom.route = bom_route
                    if hasattr(product, 'boms'):
                        product.boms += (product_bom,)
                    else:
                        product.boms = [product_bom]

            if 'purchasable' in setup.fields:
                template.purchasable = record.purchasable
                if record.purchasable:
                    template.purchase_uom = template.default_uom
                else:
                    template.purchase_uom = None

            if 'salable' in setup.fields:
                template.salable = record.salable
                if record.salable:
                    template.sale_uom = template.default_uom
                else:
                    template.sale_uom = None

            for field in ('account_revenue', 'account_depreciation',
                          'account_expense', 'account_asset'):
                if field in setup.fields:
                    template.type = 'assets'
                    template.depreciable = True
                    template.accounts_category = False
                    template.taxes_category = False
                    account_code = getattr(record, field)
                    account = cache.accounts.get(account_code)
                    setattr(template, field, account)

            if 'depreciation_percentatge' in setup.fields:
                template.depreciation_percentatge = Decimal(record.depreciation_percentatge)/100
                if hasattr(Template, 'depreciation_duration'):
                    template.depreciation_duration = (100/Decimal(record.depreciation_percentatge))*12

            if 'depreciation_duration' in setup.fields:
                if record.depreciation_duration:
                    template.depreciation_duration = record.depreciation_duration

            if cache.parties and 'supplier' in setup.fields:
                party = cache.parties.get(record.supplier)
                supplier = ProductSupplier()
                supplier.party = party
                supplier.code = record.supplier_code
                if record.supplier_currency:
                    supplier.currency = cache.currencies.get('supplier_currency')
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
                cache.templates[record.template_code] = template

                if 'brand' in setup.fields and record.brand:
                    if record.brand:
                        brand = cache.brands.get(record.brand)
                        if not brand:
                            brand = Brand()
                            brand.name = record.brand
                            cache.brands[record.brand] = brand
                    else:
                        brand = None
                    template.brand = brand

            if 'variant_suffix_code' in setup.fields:
                product.suffix_code = record.variant_suffix_code
            if 'list_price' in setup.fields:
                product.list_price = record.sale_price or Decimal(0)
            if 'cost_price' in setup.fields:
                product.cost_price = record.cost_price or Decimal(0)
            if 'description' in setup.fields:
                product.description = record.description

            # If product exist the packages are set all new, not updated.
            if 'packages' in setup.fields and record.packages:
                packages = []
                for package in record.packages.split('|'):
                    name, quantity, is_default = package.split(';')
                    ppackage = Package()
                    ppackage.name = name
                    ppackage.quantity = quantity
                    ppackage.is_default = True if is_default == '1' else False
                    packages.append(ppackage)
                template.packages = packages

            if 'template_note' in setup.fields:
                note = Note()
                note.resource = template
                note.message = record.template_note
                notes_to_save.append(note)
            if 'product_note' in setup.fields:
                note = Note()
                note.resource = product
                note.message = record.product_note
                notes_to_save.append(note)
            record.importer_template(template)
            record.importer_product(product)
            cache.templates[record.template_code] = template

        cls.importer_save(categories_to_save)
        cls.importer_save(to_save)
        cls.importer_save(products_to_save)
        cls.importer_save(notes_to_save)
        return to_save


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

class ImporterProductStockProductLocationDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    location = fields.Char('Location')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.locations = Cache('stock.location', 'name')

    def importer_template(self, template):
        pool = Pool()
        Location = pool.get('stock.location')
        ProductLocation = pool.get('stock.product.location')

        setup = Setup.get()
        cache = setup.cache
        if 'location' in setup.fields:
            warehouse = Location.get_default_warehouse()
            product_location = ProductLocation()
            product_location.warehouse = warehouse
            location = cache.locations.get(self.location)
            if not location:
                location = Location()
                location.name = self.location
                cache.locations[self.location] = location
            product_location.location = location
            template.locations = (product_location,)


class ImporterProductSupplierMinimumDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    supplier_minimum_quantity = fields.Float('Supplier Minimum Quantity')


class ImporterProductSupplierMultipleDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    supplier_multiple_quantity = fields.Float('Supplier Multiple Quantity')

class ImporterProductAccountingDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    account_expense = fields.Char('Account Expense')
    account_revenue = fields.Char('Account Revenue')

class ImporterProductAssetDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    depreciation_duration = fields.Integer('Depreciation Duration')

class ImporterProductAccountingAssetDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    account_depreciation = fields.Char('Account Depreciation')
    account_asset = fields.Char('Account Asset')

class ImporterProductAccountAssetPercentatgeDepends(metaclass=PoolMeta):
    __name__ = 'importer.product'

    depreciation_percentatge = fields.Char('Depreciation Percentatge')

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
                    'chunked': False,
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
