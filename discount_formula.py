from decimal import Decimal
from trytond.model import fields, ModelView
from trytond.pool import PoolMeta


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    discount_formula = fields.Char('Discount Formula')


class ImporterProductSupplier(metaclass=PoolMeta):
    __name__ = 'importer.product.supplier'

    base_price = fields.Numeric('Base Price')
    discount_formula = fields.Char('Discount Formula')

    def importer_product_supplier(self, supplier):
        super().importer_product_supplier(supplier)
        if self.unit_price is None:
            if self.base_price is not None:
                self.unit_price = self.base_price

    def importer_price(self, price):
        super().importer_price(price)

        if self.base_price is not None:
            price.base_price = self.base_price.quantize(Decimal('0.0001'))
        if self.discount_formula is not None:
            price.discount_formula = self.discount_formula
            price.on_change_discount_formula()
            if not price.unit_price:
                # TODO: Fix this
                price.unit_price = Decimal(0)


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)
        if record.discount_formula is not None:
            line.discount_formula = record.discount_formula

