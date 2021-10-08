from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterProduct(ModelView):
    'Importer Product'
    __name__ = 'importer.product'

    code = fields.Char('Code')
    variant_code = fields.Char('Variant Code')
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

class ImporterProductCodes(ModelView):
    'Importer Product'
    __name__ = 'importer.product_codes'

    template_code = fields.Char('Template Code')
    variant_code = fields.Char('Variant Code')
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
        Template = pool.get('product.template')
        Identifier = pool.get('product.identifier')

        products = dict((x.code, x) for x in Product.search([]))
        templates = dict((x.code, x) for x in Template.search([]))
        to_save = []
        for record in records:
            if not record.code:
                continue
            identifier = Identifier()
            identifier.type = record.type_
            code = record.template_code + record.variant_code
            product = products.get(code)
            identifier.code = record.code
            if not product:
                template = templates.get(record.template_code)
                product = template.products[0]
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
        try:
            ProductSupplier = pool.get('purchase.product_supplier')
            Party = pool.get('party.party')
            parties = dict((x.code, x) for x in Party.search([]))
        except:
            pass

        customs = {}
        try:
            TariffCodeRel = pool.get('product-customs.tariff.code')
            TariffCode = pool.get('customs.tariff.code')
            customs = dict((x.code, x) for x in TariffCode.search([]))
        except:
            pass

        categories = dict((x.name, x) for x in ProductCategory.search([]))
        uoms = {}
        for uom in Uom.search([]):
            uoms[uom.name] = uom
            uoms[uom.symbol] = uom

        products = dict((x.code, x) for x in Product.search([]))
        templates = dict((x.code, x) for x in Template.search([]))
        to_save = []
        for record in records:
            if record.code in templates and record.variant_code in products:
                continue

            if record.code not in templates:
                template = Template()
                to_save.append(template)

                template.name = record.name
                template.code = record.code
                template.list_price = record.sale_price or Decimal(0)
                uom = uoms.get(record.uom and record.uom.capitalize() or 'u')
                if not uom:
                    uom = Uom()
                    uom.name = record.uom.capitalize()
                    uom.symbol = record.uom.capitalize()
                    uom.category = uoms.get('u').category
                    uom.rate = 1
                    uom.on_change_rate()
                    uoms[uom.name] = uom

                template.default_uom = uom
                template.cost_price_method = record.cost_price_method

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
                    template.volume_uom = uoms.get('m³')

                if 'tariff_codes' in template._fields and record.aranzel:
                    custom = customs.get(record.aranzel)
                    if not customs:
                        custom = TariffCode()
                        custom.code = record.aranzel
                        customs[record.aranzel] = customs

                    rel = TariffCodeRel()
                    rel.tariff_code = custom
                    template.tariff_codes = [rel]

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

                if 'product_suppliers' in template._fields :
                    template.purchase_uom = uom
                    template.purchasable = True

                if parties and record.supplier:
                    party = parties.get(record.supplier)
                    supplier = ProductSupplier()
                    supplier.party = party
                    supplier.code = record.supplier_code
                    template.product_suppliers = [supplier]

                template.products = []
                templates[record.code] = template
            else:
                template = templates.get(record.code)

            product = Product()
            product.suffix_code = record.variant_code or ''
            product.cost_price = record.cost_price or Decimal(0)
            if 'wine_likely_alcohol_content' in product._fields:
                product.wine_likely_alcohol_content = record.alcohol_content
            template.products += (product,)
            products[record.code+(record.variant_code or '')] = product
            template.products = [product]

        ProductCategory.save(categories.values())
        Template.save(to_save)
        return to_save
