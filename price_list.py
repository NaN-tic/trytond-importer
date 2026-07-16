from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterPriceList(ImporterModel):
    'Importer Price List'
    __name__ = 'importer.price_list'

    name = fields.Char('Name')
    company_name = fields.Char('Company Name')
    tax_included = fields.Boolean('Tax Included')
    category = fields.Char('Category')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Quantity')
    formula = fields.Char('Formula')
    base_price_formula = fields.Char('Base Price Formula')

    @classmethod
    def importer_line_hook(cls, record, line):
        Pool().get('importer')._import_price_list_line_hook(record, line)

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Company = pool.get('company.company')
        PriceList = pool.get('product.price_list')
        Line = pool.get('product.price_list.line')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Category = pool.get('product.category')

        records = list(records)
        if any([x.product_code for x in records]):
            with Transaction().set_context(active_test=False):
                products = {x.code: x for x in Product.search([])}
        else:
            products = {}
        if any([x.category for x in records]):
            categories = {x.rec_name: x for x in Category.search([])}
        else:
            categories = {}
        companies = {x.rec_name: x for x in Company.search([])}

        price_list = None
        lists_to_save = []
        lines_to_save = []
        previous_name = None
        products_to_save = []
        templates_to_save = []
        for record in records:
            if record.name and record.name != previous_name:
                previous_name = record.name
                price_list = PriceList()
                price_list.name = record.name
                price_list.tax_included = record.tax_included
                if record.company_name:
                    company = companies.get(record.company_name)
                    if not company:
                        raise UserError(gettext(
                                'importer.msg_company_not_found',
                                company=record.company_name))
                    price_list.company = companies.get(record.company_name)
                lists_to_save.append(price_list)

            if not price_list:
                continue

            line = Line()
            line.price_list = price_list
            if record.product_code:
                product = products.get(record.product_code)
                if not product:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))
                if product.active == False:
                    product.active = True
                    products_to_save.append(product)
                    if product.template.active == False:
                        product.template.active  = True
                        templates_to_save.append(product.template)
                line.product = product
            if record.category:
                category = categories.get(record.category)
                if not category:
                    raise UserError(gettext(
                            'importer.product_category_not_found',
                            category=record.category))
                line.category = category
            line.quantity = record.quantity
            line.formula = record.formula
            if hasattr(line, 'base_price_formula'):
                line.base_price_formula = record.base_price_formula
            cls.importer_line_hook(record, line)
            lines_to_save.append(line)

        PriceList.save(lists_to_save)
        Line.save(lines_to_save)
        if products_to_save:
            Product.save(products_to_save)
        if templates_to_save:
            Template.save(templates_to_save)
        return lists_to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'price_list': {
                    'string': 'Price List',
                    'model': 'importer.price_list',
                    },
                })
        return methods

    @classmethod
    def _import_price_list_line_hook(cls, record, line):
        pass
