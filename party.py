from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from stdnum import get_cc_module

class ImporterParty(ModelView):
    'Importer Party'
    __name__ = 'importer.party'

    code = fields.Char('Code')
    name = fields.Char('Name')
    trade_name = fields.Char('Trade Name')
    language = fields.Char('Language')
    street = fields.Char('Street')
    postal_code = fields.Char('Postal Code')
    city = fields.Char('City')
    subdivision = fields.Char('Subdivision')
    country = fields.Char('Country')
    phone = fields.Char('Phone')
    fax = fields.Char('Fax')
    email = fields.Char('E-Mail')
    website = fields.Char('Website')
    categories = fields.Char('Categories')
    customer_payment_term = fields.Char('Customer Payment Term')
    customer_payment_type = fields.Char('Customer Payment Type')
    supplier_payment_term = fields.Char('Supplier Payment Term')
    supplier_payment_type = fields.Char('Supplier Payment Type')
    bank_account = fields.Char('Bank Account')
    customer_payment_days = fields.Char('Customer Payment days')
    supplier_payment_days = fields.Char('Supplier Payment days')
    vat = fields.Char('Vat')


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
        PartyCategory = pool.get('party.category')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        Lang = pool.get('ir.lang')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        PartyIdentifier = pool.get('party.identifier')

        import_account_fields = True
        try:
            PaymentTerm = pool.get('account.invoice.payment_term')
            PaymentTermLine = pool.get('account.invoice.payment_term.line')
            PaymentType = pool.get('account.payment.type')
            payment_terms = dict([(x.name, x) for x in PaymentTerm.search([])])
            payment_types = dict([(x.name, x) for x in
                PaymentType.search([])])
        except:
            import_account_fields = False

        languages = dict([(x.code, x) for x in Lang.search([])])
        categories = dict([(x.name, x) for x in PartyCategory.search([])])
        countries = dict([(x.code, x) for x in Country.search([])])
        subdivisions = dict([(x.name, x) for x in Subdivision.search([])])
        vats = {}
        to_save = []
        for record in records:
            party = Party()
            to_save.append(party)

            party.name = record.name
            party.code = record.code
            if hasattr(party, 'trade_name'):
                party.trade_name = record.comercial_name

            addresses = []
            address = Address()
            address.street = record.street
            address.postal_code = record.postal_code
            address.city = record.city
            country = countries.get(record.country)
            address.country = country
            subdivision = record.subdivision and record.subdivision.capitalize()
            subdivision = subdivisions.get(subdivision)
            if (subdivision and country):
                if subdivision in country.subdivisions:
                    address.subdivision = subdivision
            if (subdivision and not country):
                address.subdivision = subdivision
                address.country = subdivision.country
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
            if record.fax:
                contact = ContactMechanism()
                contact.type = 'fax'
                contact.value = record.fax
                contacts.append(contact)
            party.contact_mechanisms = contacts

            if import_account_fields:
                payment_term = payment_terms.get(record.customer_payment_term)
                if (record.customer_payment_term and not payment_term):
                    payment_term = PaymentTerm(
                        name=record.customer_payment_term)
                    payment_term.lines = [PaymentTermLine(type='remainder')]

                if payment_term:
                    party.customer_payment_term = payment_term

                payment_term = payment_terms.get(record.supplier_payment_term)
                if (record.supplier_payment_term and not payment_term):
                    payment_term = PaymentTerm(
                        name=record.supplier_payment_term)
                    payment_term.lines = [PaymentTermLine(type='remainder')]

                if payment_term:
                    party.supplier_payment_term = payment_term

                payment_type = payment_types.get(record.customer_payment_type)
                if (record.customer_payment_type and not payment_type):
                    payment_type = PaymentType(name=record.customer_payment_type)
                    payment_type.kind = 'receivable'
                    payment_type.account_bank = 'none'

                    if payment_type and record.customer_payment_type:
                        party.customer_payment_type = payment_type

                payment_type = payment_types.get(record.supplier_payment_type)
                if (record.supplier_payment_type and not payment_type):
                    payment_type = PaymentType(name=record.supplier_payment_type)
                    payment_type.kind = 'payable'
                    payment_type.account_bank = 'none'

                    if payment_type and record.supplier_payment_type:
                        party.supplier_payment_type = payment_type

            if (record.customer_payment_days and
                    hasattr(party, 'customer_paryment_days')):
                party.customer_payment_days = record.customer_payment_days

            if (record.supplier_payment_days and
                    hasattr(party, 'supplier_paryment_days')):
                party.supplier_payment_days = record.supplier_payment_days

            if record.vat:
                vat = "%s%s" % (record.country, record.vat)
                vat_type = 'eu_vat'
                if vat in vats:
                    vat_type = None

                module = get_cc_module(*['eu', 'vat'])
                if not module.is_valid(vat):
                    vat_type = None

                party_identifier = PartyIdentifier()
                party_identifier.type = vat_type
                party_identifier.code = vat
                party.identifiers = (party_identifier,)
                vats[vat] = record.code

            if record.categories:
                cats = []
                for cat in record.categories.split('|'):
                    category = categories.get(cat)
                    if not category and cat:
                        category = PartyCategory()
                        category.name = cat
                    if category:
                        cats += [category]
                        categories[cat] = category

                party.categories = cats

        PartyCategory.save(categories.values())
        Party.save(to_save)
        return to_save
