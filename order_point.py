from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterOrderPoint(ImporterModel):
    'Importer Stock Move'
    __name__ = 'importer.order_point'

    warehouse_location = fields.Char('Warehouse Location')
    product_code = fields.Char('Product Code')
    min_quantity = fields.Float('Minimum Quantity')
    target_quantity = fields.Float('Target Quantity')
    type_ = fields.Char('Type')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        OrderPoint = pool.get('stock.order_point')

        location_codes = [x.warehouse_location for x in records]
        locations = {x.code: x for x in Location.search([
            ('code', 'in', location_codes),
            ('type', '=', 'warehouse'),
            ])}

        codes = [x.product_code for x in records]
        products = {x.code: x for x in Product.search([('code', 'in', codes)])}

        company = Transaction().context.get('company')
        to_save = []
        for record in records:
            values = OrderPoint.default_get(
                    list(OrderPoint._fields.keys()), with_rec_name=False)
            order_point = OrderPoint(**values)
            order_point.company = company
            warehouse = locations.get(record.warehouse_location)
            product = products.get(record.product_code)

            if (not warehouse or not product):
                raise UserError(gettext('importer.order_point_not_value',
                    warehouse=warehouse,
                    product=product))

            type_ = record.type_
            if type_ not in ('purchase', 'production'):
                raise UserError(gettext(
                    'importer.order_point_type_not_supported',
                    type_= type_))

            order_point.warehouse_location = warehouse
            order_point.product = product
            order_point.min_quantity = record.min_quantity
            order_point.target_quantity = record.target_quantity
            order_point.type_ = type_
            to_save.append(order_point)

        OrderPoint.save(to_save)
        return to_save



class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'order_point': {
                    'string': 'Order Point',
                    'model': 'importer.order_point',
                    },
                })
        return methods




