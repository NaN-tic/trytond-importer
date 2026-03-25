from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel, Setup, Cache


class ImporterLot(ImporterModel):
    'Importer Lot'
    __name__ = 'importer.lot'
    product_code = fields.Char('Product Code')
    number = fields.Char('Number')
    date = fields.Date('Date')
    expiration_date = fields.Date('Expiry Date')
    shelf_life_expiration_date = fields.Date('Shelf Life Expiration Date')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.products = Cache('product.product', 'code')
        cache.lots = Cache('stock.lot', lambda x: (
                x.product.code and x.product.code.lower(),
                x.number.lower()),
                required=False)

    @classmethod
    def importer_lot(cls, record, lot):
        pass

    @classmethod
    def importer_import(cls, records):
        Lot = Pool().get('stock.lot')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        for record in records:
            setup.current_record = record
            lot = cache.lots.get((record.product_code, record.number))
            if not lot:
                lot = Lot()
                lot.number = record.number
                lot.product = cache.products.get(record.product_code)
                if not lot.product:
                    continue
                cache.lots.add(lot)
            if 'expiration_date' in setup.fields:
                lot.expiration_date = record.expiration_date
            if 'date' in setup.fields:
                lot.lot_date = record.date
            if 'shelf_life_expiration_date' in setup.fields:
                lot.shelf_life_expiration_date = (
                    record.shelf_life_expiration_date)
            cls.importer_lot(record, lot)
            to_save.append((lot, record))

        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'lot': {
                    'string': 'Lot',
                    'model': 'importer.lot',
                    },
                })
        return methods
