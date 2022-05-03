from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    gross_unit_price = fields.Numeric('Gross Unit Price')
    discount = fields.Numeric('Discount')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.gross_unit_price


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        pool = Pool()
        Line = pool.get('sale.line')

        super()._import_sale_line_hook(record, line)

        print(Line.gross_unit_price)
        if record.gross_unit_price is not None:
            exp = Decimal(str(10.0 ** -Line.gross_unit_price.digits[1]))

            line.gross_unit_price = record.gross_unit_price.quantize(
                exp)
            line.discount = record.discount
            line.update_prices()

