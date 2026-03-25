from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.product import round_price
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
        try:
            Lot = pool.get('stock.lot')
        except KeyError:
            Lot = None

        super().importer_start()
        setup = Setup().get()
        cache = setup.cache

        cache.locations = Cache('stock.location', 'name')
        cache.products = Cache('product.product', 'code')
        cache.currencies = Cache('currency.currency', 'code')
        if Lot:
            cache.lots = Cache('stock.lot', lambda x: (x.number
                and x.number.lower(), x.product.code and x.product.code.lower()))
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

            if 'inverted' in setup.method:
                record.from_location, record.to_location = (record.to_location,
                    record.from_location)

            if not record.quantity:
                record.quantity = 0
            if record.quantity < 0:
                record.from_location, record.to_location = (record.to_location,
                    record.from_location)
                record.quantity = -record.quantity

            from_location = cache.locations.get(record.from_location)
            to_location = cache.locations.get(record.to_location)
            product = cache.products.get(record.product_code)

            if (not product or not record.quantity or not from_location
                    or not to_location):
                continue

            move = Move()
            move.from_location = from_location
            move.to_location = to_location
            move.product = product
            move.quantity = record.quantity
            if 'cost_price' in setup.fields:
                move.cost_price = round_price(record.cost_price)
            if 'unit_price' in setup.fields:
                move.unit_price = round_price(record.unit_price)
            move.unit = cache.uoms[product.id]
            move.effective_date = record.effective_date
            move.planned_date = record.planned_date
            if 'currency' in setup.fields and record.currency:
                move.currency = cache.currencies.get(record.currency)
            if Lot and 'lot' in setup.fields and record.lot:
                move.lot = cache.lots.get((record.lot, record.product_code))
            to_save.append((move, record))

        setup.current_record = None
        cls.importer_save(to_save)

        if 'and_do' in setup.method:
            # Avoid warnings because of missing origin
            with Transaction().set_context(_skip_warnings=True):
                Move.do([x[0] for x in to_save if x[0].id and x[0].id > 0])
        return [x[0] for x in to_save]


class ImporterLocation(ImporterModel):
    'Importer Location'
    __name__ = 'importer.location'
    name = fields.Char('Name')
    parent = fields.Char('Parent')
    code = fields.Char('Code')
    type = fields.Char('Type')
    input_location = fields.Char('Input Location')
    output_location = fields.Char('Output Location')
    storage_location = fields.Char('Storage Location')
    picking_location = fields.Char('Picking Location')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        Setup.get().cache.locations = Cache('stock.location', 'name')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Location = pool.get('stock.location')

        cache = Setup.get().cache

        to_save = []
        by_name = {}
        for record in records:
            if not record.name:
                continue

            location = cache.locations.get(record.name)
            new_location = location is None
            if new_location:
                location = Location()
                location.name = record.name

            if record.code is not None:
                location.code = record.code
            if record.type is not None:
                if new_location and record.type == 'warehouse':
                    location.type = 'view'
                else:
                    location.type = record.type

            to_save.append((location, record))
            by_name[record.name] = location

        cls.importer_save(to_save)
        for location in by_name.values():
            cache.locations.add(location)

        to_save_parents = []
        to_save_warehouses = []
        for location, record in to_save:
            if record.parent is not None:
                location.parent = by_name.get(record.parent) or cache.locations.get(
                    record.parent)

            if record.type == 'warehouse':
                location.type = 'warehouse'
                if record.input_location is not None:
                    location.input_location = (
                        by_name.get(record.input_location)
                        or cache.locations.get(record.input_location))
                if record.output_location is not None:
                    location.output_location = (
                        by_name.get(record.output_location)
                        or cache.locations.get(record.output_location))
                if record.storage_location is not None:
                    location.storage_location = (
                        by_name.get(record.storage_location)
                        or cache.locations.get(record.storage_location))
                if record.picking_location is not None:
                    location.picking_location = (
                        by_name.get(record.picking_location)
                        or cache.locations.get(record.picking_location))
                to_save_warehouses.append((location, record))
            else:
                to_save_parents.append((location, record))

        cls.importer_save(to_save_parents)
        cls.importer_save(to_save_warehouses)
        return [x[0] for x in to_save]


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'location': {
                    'string': 'Location',
                    'model': 'importer.location',
                    },
                'stock_move': {
                    'string': 'Stock Move',
                    'model': 'importer.stock.move',
                    },
                'stock_move_inverted': {
                    'string': 'Stock Move (Inverted)',
                    'model': 'importer.stock.move',
                    },
                'stock_move_and_do': {
                    'string': 'Stock Move (and Do)',
                    'model': 'importer.stock.move',
                    },
                'stock_move_and_do_inverted': {
                    'string': 'Stock Move (Inverted + Do)',
                    'model': 'importer.stock.move',
                    },
                })
        return methods
