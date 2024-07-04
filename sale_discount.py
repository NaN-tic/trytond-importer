from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.modules.product import round_price


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    base_price = fields.Numeric('Base Price')
    discount_rate = fields.Numeric('Discount Rate')
    discount_amount = fields.Numeric('Discount Amount')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)

        if record.base_price is not None:
            line.base_price = round_price(record.base_price)
            line.discount_rate = record.discount_rate
            line.discount_amount = round_price(record.discount_amount)
