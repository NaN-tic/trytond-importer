from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel, Setup


class ImporterActivityType(ImporterModel):
    'Importer Activity Type'
    __name__ = 'importer.activity.type'

    name = fields.Char('Name')
    default_duration = fields.Char('Default Duration')
    active = fields.Boolean('Active')
    color = fields.Char('Color')
    sequence = fields.Char('Sequence')
    default_description = fields.Char('Default Description')

    @classmethod
    def importer_activity_type_hook(cls, record, type):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ActivityType = pool.get('activity.type')

        setup = Setup.get()

        to_save = []
        for record in records:
            setup.current_record = record

            type = ActivityType()
            if 'name' in setup.fields:
                type.name = record.name
            if 'default_duration' in setup.fields:
                type.default_duration = record.default_duration
            if 'active' in setup.fields:
                type.active = record.active
            if 'color' in setup.fields:
                type.color = record.color
            if 'sequence' in setup.fields:
                type.sequence = record.sequence
            if 'default_description' in setup.fields:
                type.default_description = record.default_description

            cls.importer_activity_type_hook(record, type)
            to_save.append((type, record))
        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'activity_type': {
                    'string': 'Activity Type',
                    'model': 'importer.activity.type',
                    }
                })
        return methods
