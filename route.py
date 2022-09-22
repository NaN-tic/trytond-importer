from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterRoute(ModelView):
    'Importer Stock Move'
    __name__ = 'importer.production_routes'

    name = fields.Char('Route name')
    uom = fields.Char('Uom')
    sequence = fields.Integer('Sequence')
    operation_type = fields.Char('Operation Type')
    workcenter_category = fields.Char('Work Center Category')
    time_ = fields.Integer('Time (minutes)', help='In minutes')
    calculation = fields.Char('Calculation', help='standard/fixed')
    quantity = fields.Float('Quantity')
    quantity_uom = fields.Char('Quantity Uom')
    notes=fields.Char('Notes')



class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'routes': {
                    'string': 'Production Routes',
                    'model': 'importer.production_routes',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_production_routes_header(cls, record):
        return (record.name,)

    @classmethod
    def _import_production_route_operation_hook(cls, record, operation):
        pass

    @classmethod
    def import_routes(cls, records):
        pool = Pool()
        Route = pool.get('production.route')
        RouteOperation = pool.get('production.route.operation')
        OperationType = pool.get('production.operation.type')
        WorkCenterCategory = pool.get('production.work_center.category')
        Uom = pool.get('product.uom')
        ModelData = Pool().get('ir.model.data')

        minute_uom =  ModelData.get_id('product', 'uom_minute')

        routes = dict((x.name, x) for x in Route.search([]))
        types = dict((x.name, x) for x  in OperationType.search([]))
        categories = dict((x.name,x) for x in WorkCenterCategory.search([]))
        uoms = {}
        for uom in Uom.search([]):
            uoms[uom.name.lower()] = uom
            uoms[uom.symbol.lower()] = uom

        previous_header = None
        to_save = []
        lines_to_save = []
        for record in records:
            header = cls.import_production_routes_header(record)
            if any(header) and header != previous_header:
                previous_header = header
                values = Route.default_get(list(Route._fields.keys()),
                    with_rec_name=False)
                route = routes.get(record.name)
                if not route:
                    route = Route(**values)
                    route.name = record.name
                    if record.uom:
                        route.uom = uoms.get(record.uom and record.uom.lower())
                    to_save.append(route)
                    routes[record.name] = route


            values = RouteOperation.default_get(list(
                RouteOperation._fields.keys()),with_rec_name=False)
            operation = RouteOperation(**values)
            operation.route = route
            operation.operation_type = types.get(record.operation_type)
            operation.work_center_category = categories.get(
                record.workcenter_category)
            operation.time = record.time_
            operation.time_uom = minute_uom
            if record.quantity:
                operation.quantity = record.quantity
            if record.quantity_uom:
                operation.quantity_uom = uoms.get(record.quantity_uom.lower())
            operation.calculation = record.calculation
            operation.notes = record.notes
            cls._import_production_route_operation_hook(record, operation)
            lines_to_save.append(operation)

        if to_save:
            Route.save(to_save)

        if lines_to_save:
            RouteOperation.save(lines_to_save)

        return to_save






