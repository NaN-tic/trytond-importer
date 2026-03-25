from datetime import date
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel


class ImporterPlantation(ImporterModel):
    'Importer Plantation'
    __name__ = 'importer.plantation'

    plantation_code = fields.Char('Plantation Code')
    party = fields.Char('Party')
    province_sigpac = fields.Numeric('Province Sigpac')
    polygon_sigpac = fields.Numeric('Polygon Sigpac')
    parcel_sigpac = fields.Numeric('Parcel Sigpac')
    zone_sigpac = fields.Numeric('Zone Sigpac')
    recinte_sigpac = fields.Numeric('Recinte Sigpac')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Plantation = pool.get('agronomics.plantation')
        Enclosure = pool.get('agronomics.enclosure')

        parties = dict((x.code, x) for x in Party.search([]))
        plantations = {}
        to_save = []
        for record in records:
            if not record.plantation_code:
                continue
            plantation = plantations.get(record.plantation_code)
            if not plantation:
                plantation = Plantation()
                plantation.code = record.plantation_code
                plantation.party = parties.get(record.party)
                plantation.enclosures = []
                plantations[record.plantation_code] = plantation
                to_save.append(plantation)
            if record.province_sigpac:
                enclosure = Enclosure()
                enclosure.province_sigpac = record.province_sigpac
                enclosure.polygon_sigpac = record.polygon_sigpac
                enclosure.parcel_sigpac = record.parcel_sigpac
                enclosure.zone_sigpac = record.zone_sigpac
                enclosure.enclosure_sigpac = record.recinte_sigpac
                plantation.enclosures += (enclosure,)
        Plantation.save(to_save)
        return to_save



class ImporterParcel(ImporterModel):
    'Importer Parcel'
    __name__ = 'importer.parcel'

    plantation_code = fields.Char('Plantation Code')
    variety = fields.Char('Variety')
    crop = fields.Char('Crop')
    surface = fields.Numeric('Surface')
    plant_number = fields.Integer('Plant Number')
    species = fields.Char('Species')

    @classmethod
    def importer_import(cls, records):
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
                crop.save()
                crops[record.crop]=crop
            parcel.crop = crop
            variety = varieties.get(record.variety)
            if not variety:
                variety = Taxon()
                variety.name = record.variety
                variety.rank = 'variety'
                variety.selectable = True
                variety.save()
                varieties[record.variety]=variety
            parcel.variety = variety
            specie = species.get(record.species)
            if not specie:
                specie = Taxon()
                specie.name = record.species
                specie.rank = 'species'
                specie.selectable = True
                specie.save()
                species[record.species]=specie
            parcel.species = specie
            to_save.append(parcel)
        Parcel.save(to_save)
        return to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'plantation': {
                    'string': 'Plantations',
                    'model': 'importer.plantation',
                    },
                'parcel': {
                    'string': 'Parcels',
                    'model': 'importer.parcel',
                    },
                })
        return methods
