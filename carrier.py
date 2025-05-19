from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.i18n import gettext
from .tools import ImporterModel, Cache, Setup


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
            'carrier': {
                'string': 'Carrier',
                'model': 'importer.carrier',
                'chunked': True,
                },
        })
        return methods


class ImporterCarrier(ImporterModel):
    'Importer Carrier'
    __name__ = 'importer.carrier'

    product = fields.Char('Product')
    party = fields.Char('Party')
    carrier_cost_method = fields.Char('Carrier Cost Method')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.products = Cache('product.product', 'code')
        cache.parties = Cache('party.party', 'code')

    @classmethod
    def import_carrier_hook(cls, record, carrier):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Carrier = pool.get('carrier')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        for record in records:
            setup.current_record = record

            if 'product' in setup.fields:
                product = cache.products.get(record.product)
                if not product:
                    setup.error(gettext('msg_carrier_product_not_found',
                        product=record.product))
                    continue
            if 'party' in setup.fields:
                party = cache.parties.get(record.party)
                if not party:
                    setup.error(gettext('msg_carrier_party_not_found',
                        party=record.party))
                    continue

            carrier = None
            if product and party:
                carrier = Carrier()
                carrier.carrier_product = product.id
                carrier.party = party.id

            if carrier and 'carrier_cost_method' in setup.fields:
                carrier.carrier_cost_method = record.carrier_cost_method
            cls.import_carrier_hook(record, carrier)
            to_save.append((carrier, record))
        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class ImporterCarrierShipmentCost(metaclass=PoolMeta):
    'Importer Carrier Shipment Cost'
    __name__ = 'importer.carrier'

    shipment_cost_allocation_method = fields.Char(
        'Shipment Cost Allocation Method')

    @classmethod
    def import_carrier_hook(cls, record, carrier):
        super().import_carrier_hook(record, carrier)

        if carrier and hasattr(record, 'shipment_cost_allocation_method'):
                carrier.shipment_cost_allocation_method = (
                    record.shipment_cost_allocation_method)
