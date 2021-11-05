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
    bank_account = fields.Char('Iban')
    customer_payment_days = fields.Char('Customer Payment days')
    supplier_payment_days = fields.Char('Supplier Payment days')
    vat = fields.Char('Vat')
    party_relation = fields.Char('Party Relation')
    type_of_relation = fields.Char('Type of relation')

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

        try:
            Bank = pool.get('bank')
            BankAccount = pool.get('bank.account')
            AccountNumber = pool.get('bank.account.number')
            banks = dict((x.bank_code.zfill(4), x) for x in Bank.search([]))
        except:
            pass

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


        try:
            Relation = pool.get('party.relation')
            RelationType = pool.get('party.relation.type')
            relations = dict((x.name, x) for x in RelationType.search([]))
        except:
            pass

        languages = dict([(x.code, x) for x in Lang.search([])])
        categories = dict([(x.name, x) for x in PartyCategory.search([])])
        countries = dict([(x.code, x) for x in Country.search([])])
        subdivisions = dict([(x.name, x) for x in Subdivision.search([])])
        parties = dict([(x.code, x) for x in Party.search([])])

        vats = {}
        to_save = []
        relations_to_save = {}
        for record in records:
            if record.code in parties:
                print("party duplicated:", record.code, record.name)
            party = Party()
            to_save.append(party)

            parties[record.code] = party
            party.name = record.name
            party.code = record.code
            if 'trade_name' in party._fields:
                party.trade_name = record.trade_name

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
                    payment_term.save()
                    payment_terms[record.customer_payment_term] = payment_term

                if payment_term:
                    party.customer_payment_term = payment_term

                payment_term = payment_terms.get(record.supplier_payment_term)
                if (record.supplier_payment_term and not payment_term):
                    payment_term = PaymentTerm(
                        name=record.supplier_payment_term)
                    payment_term.lines = [PaymentTermLine(type='remainder')]
                    payment_term.save()
                    payment_terms[record.supplier_payment_term] = payment_term

                if payment_term:
                    party.supplier_payment_term = payment_term

                customer_payment_type = payment_types.get(
                        (record.customer_payment_type, 'receivable'))
                if (record.customer_payment_type and
                        not customer_payment_type):
                    customer_payment_type = PaymentType(
                        name=record.customer_payment_type)
                    customer_payment_type.kind = 'receivable'
                    customer_payment_type.account_bank = 'none'
                    customer_payment_type.save()
                    payment_types[(record.customer_payment_type,
                        'receivable')]=customer_payment_type

                if customer_payment_type and record.customer_payment_type:
                    party.customer_payment_type = customer_payment_type

                supplier_payment_type = payment_types.get(
                        (record.supplier_payment_type, 'payable'))
                if (record.supplier_payment_type
                        and not supplier_payment_type):
                    supplier_payment_type = PaymentType(
                            name=record.supplier_payment_type)
                    supplier_payment_type.kind = 'payable'
                    supplier_payment_type.account_bank = 'none'
                    supplier_payment_type.save()
                    payment_types[(record.supplier_payment_type,
                        'payable')] = supplier_payment_type
                if supplier_payment_type and record.supplier_payment_type:
                    party.supplier_payment_type = supplier_payment_type

            if (record.customer_payment_days and
                    'customer_payment_days' in party._fields):
                party.customer_payment_days = record.customer_payment_days

            if (record.supplier_payment_days and
                    'supplier_paryment_days' in party._fields):
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

            if record.bank_account and 'bank_accounts' in party._fields:
                party.bank_accounts = []
                for iban in record.bank_account.split(' '):
                    if len(iban) < 8:
                        continue
                    bank_code = iban[4:8]
                    bank = banks.get(bank_code)
                    if not bank:
                        print("Bank not finded for account:", iban)
                        continue
                    bank_account = BankAccount()
                    bank_account.bank = bank
                    account_number = AccountNumber()
                    account_number.account = bank_account
                    account_number.type = 'iban'
                    account_number.number = iban
                    bank_account.numbers = [account_number]
                    party.bank_accounts += (bank_account,)

            if 'relations' in party._fields and record.party_relation:
                related = parties.get(record.party_relation)
                if related:
                    type_relation = relations.get(record.type_of_relation)
                    party_relation = Relation()
                    party_relation.to = related
                    party_relation.type = type_relation
                    relations_to_save[party.code] = party_relation

        PartyCategory.save(categories.values())
        Party.save(to_save)
        if 'relations' in party._fields:
            new_parties = dict((x.code, x) for x in to_save)
            rel_save = []
            for code, relation in relations_to_save.items():
                relation.from_ = new_parties.get(code)
                rel_save.append(relation)
            Relation.save(rel_save)
        return to_save
