from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterProduct(ModelView):
    'Importer Product'
    __name__ = 'importer.product'

    template_code = fields.Char('Template Code')
    variant_code = fields.Char('Variant Code')
    variant_suffix_code = fields.Char('Variant Suffix Code')
    name = fields.Char('Name')
    description = fields.Char('Description')
    uom = fields.Char('UoM')
    sale_price = fields.Numeric('Sale Price')
    cost_price = fields.Numeric('Cost Price')
    type_ = fields.Char('Type')
    cost_price_method = fields.Char('Cost Price Method')
    supplier = fields.Char('Supplier')
    supplier_code = fields.Char('Supplier Code')
    categories = fields.Char('Categories')
    account_category = fields.Char('Account Category')
    weight = fields.Numeric('Weight (kg)')
    volume = fields.Numeric('Volume (m3)')
    aranzel = fields.Char('Aranzel')
    purchasable = fields.Boolean('Purchasable')
    salable = fields.Boolean('Salable')
    alcohol_content = fields.Char('Alcohol Content')
    brand = fields.Char('Brand')


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
    def import_product(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        ProductCategory = pool.get('product.category')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        ProductCostPriceMethod = pool.get('product.cost_price_method')

        try:
            ProductSupplier = pool.get('purchase.product_supplier')
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

        template_default_values = Template.default_get(Template._fields.keys(),
                with_rec_name=False)
        product_default_values = Product.default_get(Product._fields.keys(),
                with_rec_name=False)
        cost_price_methods = ProductCostPriceMethod.get_cost_price_methods()

        to_save = []
        products_to_save = []
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
                uom = uoms.get(record.uom.lower() or 'u')
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

            if 'weight' in template._fields and record.weight:
                template.weight = record.weight
                template.weight_uom = uoms.get('kg')

            if 'volume' in template._fields and record.volume:
                template.volume = record.volume
                template.volume_uom = uoms.get('l')

            if 'tariff_codes' in template._fields and record.aranzel:
                custom = customs.get(record.aranzel)
                if not customs:
                    custom = TariffCode()
                    custom.code = record.aranzel
                    customs[record.aranzel] = customs

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

            if 'product_suppliers' in template._fields and record.purchasable:
                template.purchasable = record.purchasable
                template.purchase_uom = uom

            if 'salable' in template._fields and record.salable:
                template.salable = record.salable
                template.sale_uom = uom

            if parties and record.supplier:
                party = parties.get(record.supplier)
                supplier = ProductSupplier()
                supplier.party = party
                supplier.code = record.supplier_code
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
            if record.cost_price:
                product.cost_price = record.cost_price
            if record.description:
                product.description = record.description
            if ('wine_likely_alcohol_content' in product._fields and
                    record.alcohol_content):
                product.wine_likely_alcohol_content = record.alcohol_content

        ProductCategory.save(categories.values())
        Template.save(to_save)
        Product.save(products_to_save)
        return to_save
