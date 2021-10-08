from datetime import date
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterPlantation(ModelView):
    'Importer Plantation'
    __name__ = 'importer.plantation'

    plantation_code = fields.Char('Plantation Code')
    party = fields.Char('Party')
    province_sigpac = fields.Numeric('Province Sigpac')
    polygon_sigpac = fields.Numeric('Polygon Sigpac')
    parcel_sigpac = fields.Numeric('Parcel Sigpac')
    zone_sigpac = fields.Numeric('Zone Sigpac')

class ImporterParcel(ModelView):
    'Importer Parcel'
    __name__ = 'importer.parcel'

    plantation_code = fields.Char('Plantation Code')
    variety = fields.Char('Variety')
    crop = fields.Char('Crop')
    surface = fields.Numeric('Surface')
    plant_number = fields.Integer('Plant Number')
    species = fields.Char('Species')

class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'plantation': {
                    'string': 'Plantations',
                    'model': 'importer.plantation',
                    'chunked': True,
                    },
                'parcel': {
                    'string': 'Parcels',
                    'model': 'importer.parcel',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_plantation(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Plantation = pool.get('agronomics.plantation')
        Enclosure = pool.get('agronomics.enclosure')

        parties = dict((x.code, x) for x in Party.search([]))
        to_save = []
        for record in records:
            plantation = Plantation()
            plantation.code = record.plantation_code
            plantation.party = parties.get(record.party)
            if record.province_sigpac:
                enclosure = Enclosure()
                enclosure.province_sigpac = record.province_sigpac
                enclosure.polygon_sigpac = record.polygon_sigpac
                enclosure.parcel_sigpac = record.parcel_sigpac
                enclosure.zone_sigpac = record.zone_sigpac
                plantation.enclosures = [enclosure]
            to_save.append(plantation)
        Plantation.save(to_save)
        return to_save

    @classmethod
    def import_parcel(cls, records):
        pool = Pool()
        Crop = pool.get('agronomics.crop')
        Plantation = pool.get('agronomics.plantation')
        Taxon = pool.get('product.taxon')
        Parcel = pool.get('agronomics.parcel')

        plantations = dict((x.code, x) for x in Plantation.search([]))
        crops = dict((x.code, x) for x in Crop.search([]))
        varieties = dict((x.name, x) for x in Taxon.search(
            [('rank', '=', 'variety')]))
        species = dict((x.name, x) for x in Taxon.search(
            [('rank', '=', 'species')]))

        to_save = []
        for record in records:
            parcel = Parcel()
            parcel.plantation = plantations.get(record.plantation_code)
            parcel.surface = record.surface
            parcel.plant_number = record.plant_number
            if not parcel.plantation:
                continue
            crop = crops.get(record.crop)
            if not crop:
                crop = Crop()
                crop.code = record.crop
                crop.name = record.crop
                crop.start_date = date(day=1, month=1, year=int(record.crop))
                crop.end_date = date(day=31, month=12, year=int(record.crop))
            parcel.crop = crop
            variety = varieties.get(record.variety)
            if not variety:
                variety = Taxon()
                variety.name = record.variety
                variety.rank = 'variety'
                variety.selectable = True
            parcel.variety = variety
            specie = species.get(record.species)
            if not specie:
                specie = Taxon()
                specie.name = record.specie
                specie.rank = 'species'
                specie.selectable = True
            parcel.species = specie
            to_save.append(parcel)
        Parcel.save(to_save)
        return to_save
