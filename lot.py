from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterLot(ModelView):
    'Importer Lot'
    __name__ = 'importer.lot'
    product_code = fields.Char('Product Code')
    number = fields.Char('Number')
    date = fields.Date('Date')
    expiration_date = fields.Date('Expiry Date')
    shelf_life_expiration_date = fields.Date('Shelf Life Expiration Date')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'lot': {
                    'string': 'Lot',
                    'model': 'importer.lot',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_lot(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Lot = pool.get('stock.lot')

        numbers = []
        product_codes = []
        for record in records:
            if record.product_code:
                product_codes.append(record.product_code)
            if record.number:
                numbers.append(record.number)

        products = dict((x.code, x) for x in
            Product.search([('code', 'in', product_codes)]))
        lots = dict(((x.product.code, x.number), x) for x in Lot.search([
                    ('number', 'in', numbers),
                    ]))

        to_save = []
        for record in records:
            lot = lots.get((record.product_code, record.number))
            if not lot:
                lot = Lot()
                lot.number = record.number
                lot.product = products.get(record.product_code)
                if not lot.product:
                    raise UserError(gettext('importer.single_product_error',
                            product=record.product_code))
            if record.expiration_date:
                lot.expiration_date = record.expiration_date
            if record.date:
                lot.lot_date = record.date
            if record.shelf_life_expiration_date:
                lot.shelf_life_expiration_date = (
                    record.shelf_life_expiration_date)
            to_save.append(lot)

        Lot.save(to_save)
        return to_save
