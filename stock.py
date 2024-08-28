from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from .tools import ImporterModel, Cache, Setup



class ImporterStockMove(ImporterModel):
    'Importer Stock Move'
    __name__ = 'importer.stock.move'

    from_location = fields.Char('From Location')
    to_location = fields.Char('To Location')
    effective_date = fields.Date('Effective Date')
    planned_date = fields.Date('Planned Date')
    product_code = fields.Char('Product Code')
    quantity = fields.Float('Quantity')
    cost_price = fields.Numeric('Cost Price')
    unit_price = fields.Numeric('Unit Price')
    lot = fields.Char('Lot')
    currency = fields.Char('Currency')

    @classmethod
    def importer_start(cls):
        pool = Pool()
        Product = pool.get('product.product')

        super().importer_start()
        setup = Setup().get()
        cache = setup.cache

        cache.locations = Cache('stock.location', 'name')
        cache.products = Cache('product.product', 'code')
        cache.currencies = Cache('currency.currency', 'code')
        cache.lots = Cache('stock.lot', ['number', lambda x: x.product.code])
        # Cache Product UOMs to prevent cache trashin of if we try to use
        # the value from cache.products
        cache.uoms = {x.id: x.default_uom for x in Product.search([])}

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Move = pool.get('stock.move')
        try:
            Lot = pool.get('stock.lot')
        except KeyError:
            Lot = None

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        for record in records:
            setup.current_record = record
            from_location = cache.locations.get(record.from_location)
            to_location = cache.locations.get(record.to_location)
            product = cache.products.get(record.product_code)

            if not product:
                continue
            if (not from_location or not to_location or not product
                    or not record.quantity):
                raise UserError(gettext('importer.stock_move_error',
                    from_location=record.from_location,
                    to_location=record.to_location,
                    product=record.product_code))

            move = Move()
            move.from_location = from_location
            move.to_location = to_location
            move.product = product
            move.quantity = round(record.quantity)
            if 'cost_price' in setup.fields:
                move.cost_price = record.cost_price
            if 'unit_price' in setup.fields:
                move.unit_price = record.unit_price
            move.unit = cache.uoms[product.id]
            move.effective_date = record.effective_date
            move.planned_date = record.planned_date
            if 'currency' in setup.fields:
                move.currency = cache.currencies.get(record.currency)
            if Lot:
                move.lot = cache.lots.get((record.lot, record.product_code))
            to_save.append(move)
        cls.importer_save(to_save)
        return to_save



class ImporterLocation(ModelView):
    'Importer Location'
    __name__ = 'importer.location'
    name = fields.Char('Name')
    parent = fields.Char('Parent')
    code = fields.Char('Code')
    type = fields.Char('Type')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'location': {
                    'string': 'Location',
                    'model': 'importer.location',
                    'chunked': True,
                    },
                'stock_move': {
                    'string': 'Stock Move',
                    'model': 'importer.stock.move',
                    'chunked': True,
                    },
                'stock_move_and_do': {
                    'string': 'Stock Move (and Do)',
                    'model': 'importer.stock.move',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_location(cls, records):
        pool = Pool()
        Location = pool.get('stock.location')

        locations = {x.name: x for x in Location.search([])}

        to_save = {}
        updated_locations = []
        for record in records:
            if not record.name:
                continue

            location = locations.get(record.name)
            if not location:
                location = Location()
                location.name = record.name
            if record.code is not None:
                location.code = record.code

            if record.parent is not None:
                if record.parent in to_save:
                    Location.save(to_save.values())
                    locations.update(to_save)
                    to_save = {}

                location.parent = locations.get(record.parent)

            if record.type is not None:
                location.type = record.type

            to_save[record.name] = location
            updated_locations.append(location)

        Location.save(to_save.values())
        return updated_locations

    @classmethod
    def import_stock_move_and_do(cls, records):
        pool = Pool()
        Move = pool.get('stock.move')

        moves = cls.import_stock_move(records)
        # Avoid warnings because of missing origin
        with Transaction().set_context({'_skip_warnings': True}):
            Move.do(moves)
        return moves
