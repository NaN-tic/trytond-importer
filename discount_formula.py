from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.modules.product import round_price


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

        if self.base_price:
            price.base_price = round_price(self.base_price)
        if self.discount_formula:
            price.discount_formula = self.discount_formula
            price.on_change_discount_formula()
        if self.unit_price is None:
            # If on_change_discount_formula set unit_price to None
            # reset it as it is required
            price.unit_price = round_price(self.unit_price)


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)
        if record.discount_formula is not None:
            line.discount_formula = record.discount_formula

