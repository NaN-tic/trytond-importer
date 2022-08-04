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


class ImporterFarmAnimal(ModelView):
    "Importer Farm Animal"
    __name__ = 'importer.farm.animal'

    animal_type = fields.Char("Animal Type")
    sex = fields.Char("Sex")
    breed = fields.Char("Breed")
    initial_location = fields.Char("Initial Location")
    arrival_date = fields.Date("Arrival Date")
    origin = fields.Char("Origin")
    number = fields.Char("Number")


class ImporterFarmMedicationEvent(ModelView):
    "Importer Farm Medication Event"
    __name__ = 'importer.farm.medication.event'

    #farm = fields.Char("Farm") #TODO: add farm?
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    feed_location = fields.Char("Feed Location")
    feed_product = fields.Char("Feed Product")
    feed_lot = fields.Char("Feed Lot")
    feed_quantity = fields.Numeric("Feed Quantity")
    end_date = fields.Date("End Date")


class ImporterFarmInseminationEvent(ModelView):
    "Importer Farm Insemination Event"
    __name__ = 'importer.farm.insemination.event'

    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    dose_bom = fields.Char("Dose BOM")


class ImporterFarmPregnancyDiagnosisEvent(ModelView):
    "Importer Farm Pregnancy Diagnosis Event"
    __name__ = 'importer.farm.pregnancy_diagnosis.event'

    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    result = fields.Char("Result")
    notes = fields.Char("Notes")


class ImporterFarmAbortEvent(ModelView):
    "Importer Farm Abort Event"
    __name__ = 'importer.farm.abort.event'

    #reference
    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    notes = fields.Char("Notes")


class ImporterFarmFarrowingEvent(ModelView):
    "Importer Farm Farrowing Event"
    __name__ = 'importer.farm.farrowing.event'

    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    live = fields.Integer("Live")
    problem = fields.Char("Problem")


class ImporterFarmWeaningEvent(ModelView):
    "Importer Farm Weaning Event"
    __name__ = 'importer.farm.weaning.event'

    #reference
    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    female_to_location = fields.Char("Female To Location")
    weaned_to_location = fields.Char("Weaned To Location")
    quantity = fields.Numeric("Quantity")


class ImporterFarmTransformationEvent(ModelView):
    "Importer Farm Transformation Event"
    __name__ = 'importer.farm.transformation.event'

    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    from_location = fields.Char("From Location")
    to_animal_type = fields.Char("To Animal Type")
    to_location = fields.Char("To Location")


class ImporterFarmReclassificationEvent(ModelView):
    "Importer Farm reclassification Event"
    __name__ = 'importer.farm.reclassification.event'

    farm = fields.Char("Farm")
    animal = fields.Char("Animal")
    timestamp = fields.DateTime("Timestamp")
    reclassification_product = fields.Char("Reclasification Product")
    to_location = fields.Char("To Location")
    weight = fields.Numeric("Weight")


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
                    },
                'farm_animal': {
                    'string': 'Farm Animal',
                    'model': 'importer.farm.animal',
                    'chunked': True,
                    },
                'farm_medication_event': {
                    'string': 'Farm Medication Event',
                    'model': 'importer.farm.medication.event',
                    'chunked': True,
                    },
                'farm_insemination_event': {
                    'string': 'Farm Insemination Event',
                    'model': 'importer.farm.insemination.event',
                    'chunked': True,
                    },
                'farm_pregnancy_diagnosis_event': {
                    'string': 'Farm Pregnancy Diagnosis Event',
                    'model': 'importer.farm.pregnancy_diagnosis.event',
                    'chunked': True,
                    },
                'farm_abort_diagnosis_event': {
                    'string': 'Farm Abort Diagnosis Event',
                    'model': 'importer.farm.abort.event',
                    'chunked': True,
                    },
                'farm_farrowing_event': {
                    'string': 'Farm Farrowing Event',
                    'model': 'importer.farm.farrowing.event',
                    'chunked': True,
                    },
                'farm_weaning_event': {
                    'string': 'Farm Weaning Event',
                    'model': 'importer.farm.weaning.event',
                    'chunked': True,
                    },
                'farm_transformation_event': {
                    'string': 'Farm Transformation Event',
                    'model': 'importer.farm.transformation.event',
                    'chunked': True,
                    },
                'farm_reclassification_event': {
                    'string': 'Farm Reclassification Event',
                    'model': 'importer.farm.reclassification.event',
                    'chunked': True,
                    },
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

    @classmethod
    def import_farm_animal(cls, records):
        pool = Pool()
        FarmAnimal = pool.get('farm.animal')
        Breed = pool.get('farm.specie.breed')
        Location = pool.get('stock.location')

        breeds = {x.name: x for x in Breed.search([])}
        locations = {x.code: x for x in Location.search([])}

        to_save = []
        for record in records:
            if not record.animal_type or not record.breed:
                continue
            if record.animal_type:
                animal = FarmAnimal()
                if record.animal_type == 'individual' and not record.sex:
                    continue
                else:
                    animal.sex = record.sex
                animal.type = record.animal_type
                if breeds.get(record.breed):
                    animal.specie = breeds.get(record.breed).specie
                animal.breed = breeds.get(record.breed)
                if record.initial_location:
                    animal.initial_location = locations.get(
                        record.initial_location)
                if record.arrival_date:
                    animal.arrival_date = record.arrival_date
                if record.origin:
                    animal.origin = record.origin
                if record.number:
                    animal.number = record.number
            to_save.append(animal)
        FarmAnimal.save(to_save)
        return to_save

    @classmethod
    def import_farm_medication_event(cls, records):
        pool = Pool()
        FarmMedicationEvent = pool.get('farm.medication.event')
        FarmAnimal = pool.get('farm.animal')
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Lot = pool.get('stock.lot')

        animals = {x.number: x for x in FarmAnimal.search([])}
        locations = {x.code: x for x in Location.search([])}
        lots = {x.number: x for x in Lot.search([])}

        codes = [x.feed_product for x in records]
        products = {x.code: x for x in Product.search([('code', 'in', codes)])}

        to_save = []
        for record in records:
            if (not record.animal or not record.feed_location or
                    not record.feed_quantity):
                continue
            medication_event = FarmMedicationEvent()
            medication_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                medication_event.animal_type = animals.get(record.animal).type
                medication_event.location = animals.get(record.animal).location
                medication_event.specie = animals.get(record.animal).specie
            medication_event.feed_location  = locations.get(
                record.feed_location)
            if record.timestamp:
                medication_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.feed_product:
                medication_event.feed_product = products.get(
                    record.feed_product)
                if products.get(record.feed_product):
                    medication_event.uom = products.get(
                    record.feed_product).default_uom.id
            if record.feed_lot:
                medication_event.feed_lot = lots.get(record.feed_lot)
            if record.end_date:
                medication_event.medication_end_date = record.end_date
            medication_event.feed_quantity = record.feed_quantity

            to_save.append(medication_event)
        FarmMedicationEvent.save(to_save)
        FarmMedicationEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_insemination_event(cls, records):
        pool = Pool()
        FarmInseminationEvent = pool.get('farm.insemination.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')
        BOM = pool.get('production.bom')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}
        boms = {x.name: x for x in BOM.search([])}

        to_save = []
        for record in records:
            if not record.farm or not record.animal:
                continue
            insemination_event = FarmInseminationEvent()
            insemination_event.farm = locations.get(record.farm)
            insemination_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                insemination_event.specie = animals.get(record.animal).specie
            if record.timestamp:
                insemination_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.dose_bom:
                insemination_event.dose_bom = boms.get(record.dose_bom)
            to_save.append(insemination_event)

        FarmInseminationEvent.save(to_save)
        FarmInseminationEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_pregnancy_diagnosis_event(cls, records):
        pool = Pool()
        PregnancyDiagnosisEvent = pool.get('farm.pregnancy_diagnosis.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}

        to_save = []
        for record in records:
            if not record.farm or not record.animal or not record.result:
                continue
            pregnancy_diagnosis_event = PregnancyDiagnosisEvent()
            pregnancy_diagnosis_event.farm = locations.get(record.farm)
            pregnancy_diagnosis_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                pregnancy_diagnosis_event.specie = animals.get(
                    record.animal).specie
            pregnancy_diagnosis_event.result = record.result
            if record.timestamp:
                pregnancy_diagnosis_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.notes:
                pregnancy_diagnosis_event.notes = record.notes

            to_save.append(pregnancy_diagnosis_event)
        PregnancyDiagnosisEvent.save(to_save)
        PregnancyDiagnosisEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_abort_diagnosis_event(cls, records):
        pool = Pool()
        FarmAbortEvent = pool.get('farm.abort.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}

        to_save = []
        for record in records:
            if not record.farm or not record.animal:
                continue
            abort_event = FarmAbortEvent()
            abort_event.farm = locations.get(record.farm)
            abort_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                abort_event.specie = animals.get(record.animal).specie
            if record.timestamp:
                abort_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.notes:
                abort_event.notes = record.notes

            to_save.append(abort_event)
        FarmAbortEvent.save(to_save)
        FarmAbortEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_farrowing_event(cls,records):
        pool = Pool()
        FarmFarrowingEvent = pool.get('farm.farrowing.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')
        FarmFarrowingProblem = pool.get('farm.farrowing.problem')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}
        farrowing_problems = {
            x.name: x for x in FarmFarrowingProblem.search([])}

        to_save = []
        for record in records:
            if not record.farm or not record.animal:
                continue
            farrowing_event = FarmFarrowingEvent()
            farrowing_event.farm = locations.get(record.farm)
            farrowing_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                farrowing_event.specie = animals.get(record.animal).specie
            if record.timestamp:
                farrowing_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.live:
                farrowing_event.live = record.live
            if record.problem:
                farrowing_event.problem = farrowing_problems.get(
                    record.problem)
            to_save.append(farrowing_event)
        FarmFarrowingEvent.save(to_save)
        FarmFarrowingEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_weaning_event(cls, records):
        pool = Pool()
        FarmWeaningEvent = pool.get('farm.weaning.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}

        to_save = []
        for record in records:
            if (not record.farm or not record.animal or
                    not record.female_to_location or
                    not record.weaned_to_location):
                continue
            weaning_event = FarmWeaningEvent()
            weaning_event.farm = locations.get(record.farm)
            weaning_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                weaning_event.specie = animals.get(record.animal).specie
            weaning_event.female_to_location = locations.get(
                record.female_to_location)
            weaning_event.weaned_to_location = locations.get(
                record.weaned_to_location)
            if record.timestamp:
                weaning_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.quantity:
                weaning_event.quantity = record.quantity

            to_save.append(weaning_event)
        FarmWeaningEvent.save(to_save)
        FarmWeaningEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_transformation_event(cls, records):
        pool = Pool()
        FarmTransformationEvent = pool.get('farm.transformation.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')

        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}

        to_save = []
        for record in records:
            if (not record.farm or not record.animal or
                not record.from_location or not record.to_animal_type):
                continue
            transformation_event = FarmTransformationEvent()
            transformation_event.farm = locations.get(record.farm)
            transformation_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                transformation_event.animal_type = animals.get(
                    record.animal).type
                transformation_event.specie = animals.get(record.animal).specie
            transformation_event.from_location = locations.get(
                record.from_location)
            transformation_event.to_animal_type = record.to_animal_type
            if record.timestamp:
                transformation_event.timestamp = cls.datetime_to_utc(
                    record.timestamp)
            if record.to_location:
                transformation_event.to_location = locations.get(
                    record.to_location)
            to_save.append(transformation_event)

        FarmTransformationEvent.save(to_save)
        FarmTransformationEvent.validate_event(to_save)
        return to_save

    @classmethod
    def import_farm_reclassification_event(cls, records):
        pool = Pool()
        FarmReclassificationEvent = pool.get('farm.reclassification.event')
        Location = pool.get('stock.location')
        FarmAnimal = pool.get('farm.animal')
        Product = pool.get('product.product')

        codes = [x.reclassification_product for x in records]
        products = {x.code: x for x in Product.search([('code', 'in', codes)])}
        locations = {x.code: x for x in Location.search([])}
        animals = {x.number: x for x in FarmAnimal.search([])}

        to_save = []
        for record in records:
            if (not record.farm or not record.animal or
                    not record.reclassification_product or
                    not record.to_location):
                continue
            reclassification_event = FarmReclassificationEvent()
            reclassification_event.farm = locations.get(record.farm)
            reclassification_event.animal = animals.get(record.animal)
            if animals.get(record.animal):
                reclassification_event.animal_type = animals.get(
                    record.animal).type
                reclassification_event.specie = animals.get(
                    record.animal).specie
            reclassification_event.reclassification_product = products.get(
                record.reclassification_product)
            reclassification_event.to_location = locations.get(
                record.to_location)
            if record.timestamp:
                reclassification_event.timestamp = cls.datetime_to_utc(
                        record.timestamp)
            if record.weight:
                reclassification_event.weight = record.weight
            to_save.append(reclassification_event)

        FarmReclassificationEvent.save(to_save)
        FarmReclassificationEvent.validate_event(to_save)
        return to_save
