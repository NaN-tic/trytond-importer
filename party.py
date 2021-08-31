from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterParty(ModelView):
    'Importer Party'
    __name__ = 'importer.party'

    code = fields.Char('Code')
    name = fields.Char('Name')
    language = fields.Char('Language')
    street = fields.Char('Street')
    postal_code = fields.Char('Postal Code')
    city = fields.Char('City')
    subdivision = fields.Char('Subdivision')
    country = fields.Char('Country')
    phone = fields.Char('Phone')
    email = fields.Char('E-Mail')
    website = fields.Char('Website')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'party': {
                    'string': 'Party',
                    'model': 'importer.party',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_party(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        Lang = pool.get('ir.lang')

        languages = dict([(x.code, x) for x in Lang.search([])])

        to_save = []
        for record in records:
            party = Party()
            to_save.append(party)

            party.name = record.name
            party.code = record.code

            addresses = []
            address = Address()
            address.street = record.street
            address.postal_code = record.postal_code
            address.city = record.city
            # TODO: Country and subdivision
            addresses.append(address)

            if record.language:
                party.lang = languages.get(record.language)

            party.addresses = addresses

            contacts = []
            if record.website:
                contact = ContactMechanism()
                contact.type = 'website'
                contact.value = record.website
                contacts.append(contact)
            if record.phone:
                contact = ContactMechanism()
                contact.type = 'phone'
                contact.value = record.phone
                contacts.append(contact)
            if record.email:
                contact = ContactMechanism()
                contact.type = 'email'
                contact.value = record.email
                contacts.append(contact)

            party.contact_mechanisms = contacts

        Party.save(to_save)
        return to_save
