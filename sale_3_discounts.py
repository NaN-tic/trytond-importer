from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.modules.product import round_price

ZERO = Decimal(0)


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    discount1 = fields.Numeric('Discount')
    discount2 = fields.Numeric('Discount')
    discount3 = fields.Numeric('Discount')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)

        update = False
        if record.discount1 is not None:
            line.discount1 = round_price(record.discount1 or ZERO)
            update = True
        if record.discount2 is not None:
            line.discount2 = round_price(record.discount2 or ZERO)
            update = True
        if record.discount3 is not None:
            line.discount3 = round_price(record.discount3 or ZERO)
            update = True
        if update:
            line.update_prices()

