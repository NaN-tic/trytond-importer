from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterFarmMoveEvent(ModelView):
    'Importer Event Move'
    __name__ = 'importer.farm.move.event'

    farm = fields.Char('Farm')
    animal = fields.Char('Animal')
    timestamp = fields.DateTime('Date & Time')
    to_location = fields.Char('To Location')
    notes = fields.Char('Notes')
    weight = fields.Numeric('Weight')


class ImporterFarmRemovalEvent(ModelView):
    'Importer Removal Event'
    __name__ = 'importer.farm.removal.event'

    farm = fields.Char('Farm')
    animal = fields.Char('Animal')
    timestamp = fields.DateTime('Date & Time')
    removal_reason = fields.Char('Reason')
    removal_type = fields.Char('Type')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'farm_move_event': {
                    'string': 'Farm Move Event',
                    'model': 'importer.farm.move.event',
                    'chunked': True,
                    },
                'farm_removal_event': {
                    'string': 'Farm Removal Event',
                    'model': 'importer.farm.removal.event',
                    'chunked': True,
                    }
                })
        return methods

    @classmethod
    def import_farm_move_event(cls, records):
        pool = Pool()
        Location = pool.get('stock.location')
        Animal = pool.get('farm.animal')
        FarmMove = pool.get('farm.move.event')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in Animal.search([])}
        to_save = []
        for record in records:
            if not record.animal or not animals.get(record.animal):
                raise UserError(
                    gettext('importer.animal_not_found', animal=record.animal))
            if not record.farm or not locations.get(record.farm):
                raise UserError(
                    gettext('importer.farm_not_found', farm=record.farm))
            if not record.to_location or not locations.get(record.to_location):
                raise UserError(gettext(
                    'importer.location_not_found', location=record.location))
            move = FarmMove()
            move.farm = locations.get(record.farm)
            move.animal = animals.get(record.animal)
            move.animal_type = move.animal.type
            move.timestamp = cls.datetime_to_utc(record.timestamp)
            move.specie = move.animal.specie
            move.unit_price = move.on_change_with_unit_price()
            move.from_location = move.animal.location
            move.to_location = locations.get(record.to_location)
            move.notes = record.notes
            move.weight = record.weight
            to_save.append(move)
        FarmMove.save(to_save)
        return to_save

    @classmethod
    def import_farm_removal_event(cls, records):
        pool = Pool()
        Location = pool.get('stock.location')
        Animal = pool.get('farm.animal')
        FarmRemoval = pool.get('farm.removal.event')
        RemovalType = pool.get('farm.removal.type')
        RemovalReason = pool.get('farm.removal.reason')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in Animal.search([])}
        removal_types = {x.name: x for x in RemovalType.search([])}
        removal_reasons = {x.name: x for x in RemovalReason.search([])}

        to_save = []
        for record in records:
            if not record.animal or not animals.get(record.animal):
                raise UserError(
                    gettext('importer.animal_not_found', animal=record.animal))
            if not record.farm or not locations.get(record.farm):
                raise UserError(
                    gettext('importer.farm_not_found', farm=record.farm))
            removal = FarmRemoval()
            removal.farm = locations.get(record.farm)
            removal.animal = animals.get(record.animal)
            removal.animal_type = removal.animal.type
            removal.timestamp = cls.datetime_to_utc(record.timestamp)
            removal.specie = removal.animal.specie
            removal.from_location = removal.animal.location
            removal.removal_type = removal_types.get(record.removal_type)
            removal.reason = removal_reasons.get(record.removal_reason)
            to_save.append(removal)
        FarmRemoval.save(to_save)
        return to_save
