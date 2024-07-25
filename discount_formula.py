from trytond.model import fields, ModelView
from trytond.pool import PoolMeta


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    discount_formula = fields.Char('Discount Formula')


class ImporterProductSupplier(ModelView):
    'Importer Product Supplier'
    __name__ = 'importer.product.supplier'

    base_price = fields.Numeric('Base Price')
    discount_formula = fields.Char('Discount Formula')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)
        if record.discount_formula is not None:
            line.discount_formula = record.discount_formula

    @classmethod
    def _import_purchase_product_supplier_hook(cls, record, supplier):
        super()._import_product_supplier_hook(record, supplier)
        if record.unit_price is None:
            if record.base_price is not None:
                record.unit_price = record.base_price

    @classmethod
    def _import_purchase_product_supplier_price_hook(cls, record, price):
        super()._import_purchase_product_supplier_price_hook(record, price)

        if record.base_price is not None:
            price.base_price = record.base_price
        if record.discount_formula is not None:
            price.discount_formula = record.discount_formula
            price.on_change_discount_formula()

