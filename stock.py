from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext



class ImporterStockMove(ModelView):
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


class ImporterLocation(ModelView):
    'Importer Location'
    __name__ = 'importer.location'
    name = fields.Char('Name')
    parent = fields.Char('Parent')
    code = fields.Char('Code')


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
            to_save[record.name] = location
            updated_locations.append(location)

        Location.save(to_save.values())
        return updated_locations

    @classmethod
    def import_stock_move(cls, records):
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Lot = pool.get('stock.lot')

        location_names = ([x.from_location for x in records] +
            [x.to_location for x in records])
        locations = {x.name: x for x in Location.search([
            ('name', 'in', location_names)])}

        codes = [x.product_code for x in records]
        products = {x.code: x for x in Product.search([('code', 'in', codes)])}

        lots = {}
        if hasattr(Move, 'lot'):
            for record in records:
                if record.lot:
                    domain = [
                        ('number', '=', record.lot),
                        ('product.code', '=', record.product_code)
                        ]
                    if hasattr(Move, 'expiration_date'):
                        domain.append(
                            ('expiration_date', '>=', record.effective_date))
                    lots_ = Lot.search(domain)
                    if lots_:
                        lot = lots_[0]
                        lots[(lot.number, record.product_code)] = lot

        to_save = []
        for record in records:
            move = Move()
            from_location = locations.get(record.from_location)
            to_location = locations.get(record.to_location)
            product = products.get(record.product_code)
            lot = lots.get((record.lot, record.product_code))

            if (not from_location or not to_location or not product
                    or not record.quantity):
                raise UserError(gettext('importer.stock_move_error',
                    from_location=record.from_location,
                    to_location=record.to_location,
                    product=record.product_code))

            move.from_location = from_location
            move.to_location = to_location
            move.product = product
            move.quantity = record.quantity
            move.cost_price = record.cost_price
            move.unit_price = record.unit_price
            move.uom = product.default_uom
            move.effective_date = record.effective_date
            move.planned_date = record.planned_date
            if lot:
                move.lot = lot
            to_save.append(move)
        Move.save(to_save)
        return to_save

    @classmethod
    def import_stock_move_and_do(cls, records):
        pool = Pool()
        Move = pool.get('stock.move')

        moves = cls.import_stock_move(records)
        # Avoid warnings because of missing origin
        with Transaction().set_context({'_skip_warnings': True}):
            Move.do(moves)
        return moves
