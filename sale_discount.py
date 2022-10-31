from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.modules.product import round_price


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    gross_unit_price = fields.Numeric('Gross Unit Price')
    discount = fields.Numeric('Discount')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)

        if record.gross_unit_price is not None:
            line.gross_unit_price = round_price(record.gross_unit_price)
            line.discount = record.discount
            line.update_prices()
