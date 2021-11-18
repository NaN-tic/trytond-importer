from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterProduct(ModelView):
    'Importer Product'
    __name__ = 'importer.product'

    code = fields.Char('Code')
    name = fields.Char('Name')
    uom = fields.Char('UoM')
    sale_price = fields.Numeric('Sale Price')
    cost_price = fields.Numeric('Cost Price')


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
                })
        return methods

    @classmethod
    def import_product(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        uoms = {}
        for uom in Uom.search([]):
            uoms[uom.name] = uom
            uoms[uom.symbol] = uom

        # To search existen products use the product_product code, so if the
        # unique variant is not installed, some products could be not update
        # correctly.
        record_codes = []
        for record in records:
            if record.code:
                record_codes.append(record.code)
        record_codes = Product.search([
                ('code', 'in', record_codes)
                ])
        record_codes = {x.code: x for x in record_codes}

        to_save = []
        to_update = []
        for record in records:
            if record.code in record_codes:
                product = record_codes[record.code]
                if record.name:
                    product.name = record.name
                if record.sale_price:
                    product.list_price = record.sale_price
                if record.uom:
                    product.default_uom = uoms.get(record.uom or 'u')
                if record.cost_price:
                    product.cost_price = record.cost_price
                to_update.append(product)
            else:
                template = Template()
                to_save.append(template)

                template.name = record.name
                template.list_price = record.sale_price or Decimal(0)
                template.default_uom = uoms.get(record.uom or 'u')

                product = Product()
                product.code = record.code
                product.cost_price = record.cost_price or Decimal(0)

                template.products = [product]

        if to_save:
            Template.save(to_save)
        if to_update:
            Product.save(to_update)
        return to_save + to_update
