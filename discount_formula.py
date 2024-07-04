from trytond.model import fields
from trytond.pool import PoolMeta


class ImporterSale(metaclass=PoolMeta):
    __name__ = 'importer.sale'
    discount_formula = fields.Char('Discount Formula')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _import_sale_line_hook(cls, record, line):
        super()._import_sale_line_hook(record, line)
        if record.discount_formula is not None:
            line.discount_formula = record.discount_formula

