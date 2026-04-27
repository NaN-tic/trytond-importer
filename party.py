from datetime import timedelta
from trytond.tools.email_ import validate_email
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from stdnum import get_cc_module, iban as stdnum_iban
from trytond.i18n import gettext
from .tools import ImporterModel, Cache, Setup


class ImporterPartyConfiguration(ImporterModel):
    'Importer Party Configuration'
    __name__ = 'importer.party.configuration'

    language_code = fields.Char('Language Code')
    sequence_prefix = fields.Char("Sequence prefix")
    sequence_suffix = fields.Char("Sequence suffix")
    sequence_padding = fields.Integer("Sequence Padding")
    sequence_number_next = fields.Integer("Sequence Number Next")

    @classmethod
    def importer_import(cls, records):
        pool = Pool()

        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("party.configuration")
        Lang = pool.get("ir.lang")
        ModelData = pool.get("ir.model.data")

        to_save = []
        for record in records:
            configuration = Configuration(1)

            if record.sequence_padding or record.sequence_number_next:
                sequence = configuration.party_sequence

                if not sequence:
                    sequence = Sequence()
                    sequence.name = "Party"
                    configuration.party_sequence = sequence

                sequence.sequence_type = ModelData.get_id('party',
                    'sequence_type_party')
                sequence.prefix = record.sequence_prefix
                sequence.suffix = record.sequence_suffix
                sequence.padding = record.sequence_padding
                sequence.number_next = record.sequence_number_next
                sequence.save()

            langs = Lang.search(["code", "=", record.language_code], limit=1)
            if langs:
                configuration.party_lang, = langs
            break

        Configuration.save(to_save)
        return [Configuration(1)]


class ImporterParty(ImporterModel):
    'Importer Party'
    __name__ = 'importer.party'

    company = fields.Char('Company',
        help="Company field can be used to set company-dependent fields."
        "Better sort records by company prior to import for better "
        "performance.")
    active = fields.Boolean('Active')
    code = fields.Char('Code')
    name = fields.Char('Name')
    trade_name = fields.Char('Trade Name')
    language = fields.Char('Language')
    street = fields.Char('Street')
    postal_code = fields.Char('Postal Code')
    city = fields.Char('City')
    subdivision = fields.Char('Subdivision')
    country = fields.Char('Country')
    shipment_street = fields.Char('Shipment Street')
    shipment_postal_code = fields.Char('Shipment Postal Code')
    shipment_city = fields.Char('Shipment City')
    shipment_subdivision = fields.Char('Shipment Subdivision')
    shipment_country = fields.Char('Shipment Country')
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
    note = fields.Char('Note')

    @classmethod
    def importer_start(cls):
        pool = Pool()
        Type = pool.get('party.address.subdivision_type')

        super().importer_start()

        cache = Setup.get().cache
        cache.companies = Cache('company.company',
            key=lambda x: x.party.name.lower())
        cache.banks = Cache('bank', key=lambda x: x.bank_code.zfill(4))
        cache.bank_accounts = Cache('bank.account.number', 'number_compact',
            required=False)
        cache.payment_terms = Cache('account.invoice.payment_term', 'name')
        cache.payment_types = Cache('account.payment.type',
            key=lambda x: (x.name.lower(), x.kind))
        cache.relations = Cache('party.relation.type', 'name')
        cache.tax_rules = Cache('account.tax.rule', 'name')
        cache.agents = Cache('commission.agent', key=lambda x: (x.party.code
            and x.party.code.lower(), x.plan and x.plan.name.lower()))
        cache.agents_no_plan = Cache('commission.agent', key=lambda x:
            x.party.name and x.party.name.lower())
        cache.inco_terms = Cache('incoterm', 'code')
        cache.languages = Cache('ir.lang', 'code')
        cache.categories = Cache('party.category', 'name')
        cache.currencies = Cache('currency.currency', 'code')
        cache.countries = Cache('country.country', ('code', 'name'), unaccent=True)
        cache.subdivisions = {}
        cache.postal_codes = {}
        for country in cache.countries.values():
            types = Type.get_types(country)
            cache.subdivisions[country] = Cache('country.subdivision', 'name',
                domain=[
                    ('country', '=', country),
                    ('type', 'in', types),
                    ], unaccent=True)
            cache.postal_codes[country] = Cache('country.postal_code', 'postal_code', domain=[
                    ('country', '=', country),
                    ('subdivision.type', 'in', types),
                    ], cache_size=50000)
        cache.carriers = Cache('carrier', key=lambda x:x.party.code.lower())

    def importer_context(self):
        res = super().importer_context()
        setup = Setup.get()
        if 'company' in setup.fields and self.company:
            company = setup.cache.companies.get(self.company)
            if company:
                res['company'] = company.id
        return res

    @classmethod
    def importer_context_start(cls):
        super().importer_context_start()

        cache = Setup.get().cache
        cache.parties = Cache('party.party', 'code', required=False, context={
                'active_test': False,
                })

    @classmethod
    def importer_party(cls, record, party):
        pass

    @classmethod
    def import_party_party_hook(cls, record, party):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        PartyIdentifier = pool.get('party.identifier')
        PartyCategory = pool.get('party.category')
        Note = pool.get('ir.note')

        try:
            BankAccount = pool.get('bank.account')
            AccountNumber = pool.get('bank.account.number')
        except KeyError:
            BankAccount = None
            AccountNumber = None
        try:
            PaymentTerm = pool.get('account.invoice.payment_term')
            PaymentTermLine = pool.get('account.invoice.payment_term.line')
        except KeyError:
            PaymentTerm = None
            PaymentTermLine = None
        try:
            PaymentType = pool.get('account.payment.type')
        except KeyError:
            PaymentType = None
        try:
            Relation = pool.get('party.relation')
        except KeyError:
            Relation = None

        setup = Setup.get()
        cache = setup.cache

        company = Transaction().context.get('company')
        vats = {}
        to_save = []
        categories_to_save = []
        bank_accounts_to_save = []
        notes_to_save = []
        relations_to_save = {}

        def get_bank_account(number):
            if not number:
                return None
            account_number = cache.bank_accounts.get(number.replace(" ", ""))
            if account_number:
                return getattr(account_number, 'account', account_number)

        def get_party_bank_account(party, number):
            if not number:
                return None
            number = number.replace(" ", "")
            for bank_account in party.bank_accounts:
                for account_number in bank_account.numbers:
                    if account_number.number.replace(' ', '') == number:
                        return bank_account
        for record in records:
            setup.current_record = record
            party = None
            if record.code:
                party = cache.parties.get(record.code)

            if not party:
                party = Party()
                party.code = record.code
                cache.parties[record.code] = party

            to_save.append((party, record))

            if 'active' in setup.fields:
                party.active = record.active
            if 'name' in setup.fields:
                party.name = record.name
            if 'trade_name' in setup.fields:
                party.trade_name = record.trade_name
            if 'supplier' in setup.fields:
                party.supplier = record.supplier
            if 'customer' in setup.fields:
                party.customer = record.customer

            # TODO allow days, hours... cast_value format
            if ('supplier_lead_time' in setup.fields
                    and record.supplier_lead_time):
                party.supplier_lead_time = timedelta(
                    days=record.supplier_lead_time)

            addresses = []
            address = Address()
            if hasattr(Address, 'invoice'):
                address.invoice = True
            address.street = record.street
            address.postal_code = record.postal_code
            address.city = record.city
            country = cache.countries.get(record.country)
            if not country:
                country = cache.countries.get('ES')
            address.country = country
            if hasattr(Address, 'delivery'):
                address.delivery = record.delivery_address
            if hasattr(Address, 'invoice'):
                address.invoice = record.invoice_address

            subdivision_error = None
            cs = cache.subdivisions.get(country)

            if cs and record.subdivision:
                if record.subdivision in cs:
                    address.subdivision = cs.get(record.subdivision)
                else:
                    subdivision_error = gettext('importer.msg_subdivision_not_found',
                        subdivision=record.subdivision,
                        country=country.name)

            if (not getattr(address, 'subdivision', None)
                    and record.postal_code):

                cs = cache.postal_codes.get(country)
                if cs:
                    code = cs.get(record.postal_code)
                    if code:
                        address.subdivision = code.subdivision

            if not getattr(address, 'subdivision', None) and subdivision_error:
                setup.error(subdivision_error, record)

            addresses.append(address)
            if 'language' in setup.fields:
                party.lang = cache.languages.get(record.language)

            if (record.shipment_street or record.shipment_postal_code or
                    record.shipment_city or record.shipment_subdivision or
                    record.shipment_country):
                shipment_address = Address()
                if hasattr(Address, 'shipment'):
                    shipment_address.shipment = True
                shipment_address.street = record.shipment_street
                shipment_address.postal_code = record.shipment_postal_code
                shipment_address.city = record.shipment_city
                country = cache.countries.get(record.shipment_country)
                shipment_address.country = country


                subdivision_error = None
                cs = cache.subdivisions.get(country)
                if cs and record.shipment_subdivision:
                    if record.subdivision in cs:
                        shipment_address.subdivision = cs.get(record.subdivision)
                    else:
                        subdivision_error = gettext('importer.msg_subdivision_not_found',
                            subdivision=record.subdivision,
                            country=country.name)

                if (not getattr(shipment_address, 'subdivision', None)
                        and country and country.code == 'ES'
                        and record.postal_code):
                    code = cache.postal_codes.get(record.postal_code)
                    if code:
                        shipment_address.subdivision = code.subdivision

                if not getattr(shipment_address, 'subdivision', None) and subdivision_error:
                    setup.error(subdivision_error, record)

                addresses.append(shipment_address)

            party.addresses = addresses

            contacts = []
            if record.website:
                contact = ContactMechanism()
                contact.type = 'website'
                contact.value = record.website
                contacts.append(contact)
            if record.phone:
                phones = [x.strip() for x in record.phone.split('/') if x.strip()]
                for phone in phones:
                    contact = ContactMechanism()
                    contact.type = 'phone'
                    contact.value = phone
                    contacts.append(contact)
            if record.email:
                emails = [x.strip().lower() for x in record.email.split('/') if x.strip()]
                for email in emails:
                    contact = ContactMechanism()
                    try:
                        validate_email(email)
                        contact.type = 'email'
                    except:
                        contact.type = 'other'
                    contact.value = email
                    contacts.append(contact)
            if record.fax:
                faxes = [x.strip() for x in record.fax.split('/') if x.strip()]
                for fax in faxes:
                    contact = ContactMechanism()
                    contact.type = 'fax'
                    contact.value = fax
                    contacts.append(contact)
            party.contact_mechanisms = contacts

            payment_term = cache.payment_terms.get(record.customer_payment_term)
            if (record.customer_payment_term and not payment_term):
                payment_term = PaymentTerm(name=record.customer_payment_term)
                payment_term.lines = [PaymentTermLine(type='remainder')]
                payment_term.save()
                cache.payment_terms[record.customer_payment_term] = payment_term

            if payment_term:
                party.customer_payment_term = payment_term

            payment_term = cache.payment_terms.get(record.supplier_payment_term)
            if (record.supplier_payment_term and not payment_term):
                payment_term = PaymentTerm(name=record.supplier_payment_term)
                payment_term.lines = [PaymentTermLine(type='remainder')]
                payment_term.save()
                cache.payment_terms[record.supplier_payment_term] = payment_term

            if payment_term:
                party.supplier_payment_term = payment_term

            customer_payment_type = None
            if record.customer_payment_type:
                key = (record.customer_payment_type.lower(), 'receivable')
                if not key in cache.payment_types:
                    key = (record.customer_payment_type.lower(), 'both')
                customer_payment_type = cache.payment_types.get(key)

            if (record.customer_payment_type and
                    not customer_payment_type):
                customer_payment_type = PaymentType(
                    name=record.customer_payment_type)
                customer_payment_type.kind = 'receivable'
                customer_payment_type.account_bank = 'none'
                if company:
                    customer_payment_type.company = company
                customer_payment_type.save()
                cache.payment_types[(record.customer_payment_type,
                    'receivable')]=customer_payment_type

            if customer_payment_type and record.customer_payment_type:
                party.customer_payment_type = customer_payment_type

            supplier_payment_type = None
            if record.supplier_payment_type:
                key = (record.supplier_payment_type.lower(), 'payable')
                if not key in cache.payment_types:
                    key = (record.supplier_payment_type.lower(), 'both')
                supplier_payment_type = cache.payment_types.get(key)
            if (record.supplier_payment_type
                    and not supplier_payment_type):
                supplier_payment_type = PaymentType(
                    name=record.supplier_payment_type)
                supplier_payment_type.kind = 'payable'
                supplier_payment_type.account_bank = 'none'
                if company:
                    supplier_payment_type.company = company
                supplier_payment_type.save()
                cache.payment_types[(record.supplier_payment_type,
                    'payable')] = supplier_payment_type
            if supplier_payment_type and record.supplier_payment_type:
                party.supplier_payment_type = supplier_payment_type

            if (record.customer_payment_days
                    and 'customer_payment_days' in setup.fields):
                party.customer_payment_days = record.customer_payment_days

            if (record.supplier_payment_days
                    and 'supplier_payment_days' in setup.fields):
                party.supplier_payment_days = record.supplier_payment_days

            if record.vat:
                vat = "%s%s" % (record.country, record.vat)
                vat_type = 'eu_vat'
                if vat in vats:
                    vat_type = None

                module = get_cc_module(*['eu', 'vat'])
                if not module.is_valid(vat):
                    vat_type = None

                party_identifier = None
                if party.id is not None and party.id >= 0:
                    identifiers = PartyIdentifier.search([
                            ('party', '=', party.id),
                            ('code', '=', vat),
                            ], limit=1)
                    if identifiers:
                        party_identifier = identifiers[0]
                if not party_identifier:
                    party_identifier = PartyIdentifier()
                party_identifier.type = vat_type
                party_identifier.code = vat
                party.identifiers = (party_identifier,)
                vats[vat] = record.code

            if record.categories:
                cats = []
                for cat in record.categories.split('|'):
                    category = cache.categories.get(cat)
                    if not category and cat:
                        category = PartyCategory()
                        category.name = cat
                        categories_to_save.append((category, record))
                    if category:
                        cats += [category]
                        cache.categories[cat] = category

                party.categories = cats

            if 'customer_tax_rule' in setup.fields:
                party.customer_tax_rule = cache.tax_rules.get(
                    record.customer_tax_rule)
            if 'supplier_tax_rule' in setup.fields:
                party.supplier_tax_rule = cache.tax_rules.get(
                    record.supplier_tax_rule)

            if 'default_payable_company_bank_account' in setup.fields:
                party.payable_company_bank_account = get_bank_account(
                    record.default_payable_company_bank_account)

            if 'default_receivable_company_bank_account' in setup.fields:
                party.receivable_company_bank_account = get_bank_account(
                    record.default_receivable_company_bank_account)

            if 'agent' in setup.fields and record.agent:
                new_agents = []
                CommissionAgentSelection = pool.get('commission.agent.selection')
                for agent in record.agent.split('|'):
                    if ',' in agent:
                        agent, plan = agent.split(',')
                        key = (agent, plan)
                        com_a = cache.agents.get((key))
                    else:
                        com_a = cache.agents_no_plan.get(agent)
                        plan = None

                    if not com_a:
                        setup.error(gettext('importer.agent_not_found',
                            agent=agent, plan=plan),
                            record)
                    com_agen_sel = CommissionAgentSelection()
                    com_agen_sel.agent = com_a
                    com_agen_sel.company = company
                    new_agents.append(com_agen_sel)
                party.agents = new_agents


            if hasattr(Party, 'sii_identifier_type'):
                if record.sii_identifier_type != 'None':
                    party.sii_identifier_type = record.sii_identifier_type

            if 'carrier' in setup.fields and record.carrier:
                carrier = cache.carriers.get(record.carrier)
                if not carrier:
                    setup.error(gettext('importer.msg_carrier_not_found',
                        carrier=record.carrier))
                else:
                    party.carrier = carrier

            if 'incoterm' in setup.fields:
                party.incoterm = cache.incoterms.get(record.incoterm_name)
                party.on_change_incoterm()
                party.incoterm_place = record.incoterm_place
            if 'purchase_incoterm' in setup.fields:
                party.purchase_incoterm = cache.incoterms.get(
                    record.incoterm_purchase_name)
                party.on_change_purchase_incoterm()
                party.purchase_incoterm_place = record.incoterm_purchase_place

            if 'relations' in setup.fields and record.party_relation:
                related = cache.parties.get(record.party_relation)
                if related:
                    type_relation = cache.relations.get(record.type_of_relation)
                    party_relation = Relation()
                    party_relation.to = related
                    party_relation.type = type_relation
                    relations_to_save[party.code] = party_relation

            cls.import_party_party_hook(record, party)
            cls.importer_party(record, party)

        cache.current_record = None
        cls.importer_save(categories_to_save)
        cls.importer_save(to_save)
        # If party has not been saved, do not try to save its notes

        # Discard parties that could not be saved
        to_save = [x for x in to_save if x[0].id]

        if 'note' in setup.fields:
            for party, record in to_save:
                setup.current_record = record
                if record.note:
                    for item in record.note.split('|'):
                        note = Note()
                        note.resource = party
                        note.message = item
                        notes_to_save.append((note, record))
            cls.importer_save(notes_to_save)

        if 'relations' in setup.fields:
            relations_to_save = []
            for party, record in to_save:
                setup.current_record = record
                related = cache.parties.get(record.party_relation)
                if related:
                    type_relation = cache.relations.get(record.type_of_relation)
                    party_relation = Relation()
                    party_relation.from_ = party
                    party_relation.to = related
                    party_relation.type = type_relation
                    relations_to_save.append((party_relation, record))

            cls.importer_save(relations_to_save)

        if 'bank_account' in setup.fields:
            for party, record in to_save:
                setup.current_record = record
                if record.bank_account:
                    for account in record.bank_account.split('|'):
                        if (',') in account:
                            iban, currency_code = account.split(',')
                        else:
                            iban = account
                            currency_code = 'EUR'

                        iban = iban.replace(' ', '')

                        currency = cache.currencies.get(currency_code)
                        if len(iban) < 8 or not stdnum_iban.is_valid(iban):
                            setup.error(gettext('importer.msg_wrong_iban',
                                iban=iban))
                            continue

                        bank_number = cache.bank_accounts.get(iban)
                        if not bank_number:
                            bank_code = iban[4:8]
                            bank = cache.banks.get(bank_code)
                            bank_account = BankAccount()
                            bank_account.bank = bank
                            bank_account.currency = currency
                            bank_account.owners = (party,)
                            account_number = AccountNumber()
                            account_number.account = bank_account
                            account_number.type = 'iban'
                            account_number.number = iban
                            cache.bank_accounts[iban] = account_number
                            bank_account.numbers = [account_number]
                            bank_accounts_to_save.append((bank_account, record))
                        else:
                            bank_account = bank_number.account
                            bank_account.owners += (party,)
                            if bank_account not in [x[0] for x in bank_accounts_to_save]:
                                bank_accounts_to_save.append((bank_account, record))

            cls.importer_save(bank_accounts_to_save)


        if ('default_payable_bank_account' in setup.fields
                or 'default_receivable_bank_account' in setup.fields):

            for party, record in to_save:
                setup.current_record = record
                if record.default_payable_bank_account:
                    party.payable_bank_account = get_party_bank_account(party,
                        record.default_payable_bank_account)
                if record.default_receivable_bank_account:
                    party.receivable_bank_account = get_party_bank_account(party,
                        record.default_receivable_bank_account)

            cls.importer_save(to_save)

        return [x[0] for x in to_save]

class ImporterPartyAddress(ImporterModel):
    'Importer Address'
    __name__ = 'importer.party.address'

    city = fields.Char('City')
    country_name = fields.Char('Country')
    name = fields.Char('Name')
    subdivision = fields.Char('Address Subdivision')
    street = fields.Char('Street Address')
    postal_code = fields.Char('Postal Code')
    party_code = fields.Char('Party Code')
    contact_value = fields.Char('Value')
    contact_type = fields.Char('Type')
    sequence = fields.Integer('Sequence')

    @classmethod
    def importer_start(cls):
        pool = Pool()
        Type = pool.get('party.address.subdivision_type')

        super().importer_start()

        cache = Setup.get().cache
        cache.countries = Cache('country.country', 'code', unaccent=True)
        cache.subdivisions = {}
        cache.subdivisions = {}
        for country in cache.countries.values():
            types = Type.get_types(country)
            cache.subdivisions[country] = Cache('country.subdivision', 'name',
                domain=[
                    ('country', '=', country.id),
                    ('type', 'in', types),
                ], unaccent=True)
        cache.parties = Cache('party.party', 'code')
        cache.names = Cache('party.address', 'name')
        cache.cities = Cache('party.address', 'city')

    @classmethod
    def importer_address(cls, record, address):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()

        setup = Setup.get()
        cache = setup.cache
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')

        to_save = []
        to_save_contact_mechanism = []
        for record in records:
            address = Address()
            if 'party_code' in setup.fields:
                address.party = cache.parties.get(record.party_code)
            if 'name' in setup.fields:
                address.party_name = record.name
            if 'street' in setup.fields:
                address.street = record.street
            if 'country_name' in setup.fields:
                address.country = cache.countries.get(record.country_name)
            if 'city' in setup.fields:
                address.city = record.city
            if 'subdivision' in setup.fields:
                cs = cache.subdivisions.get(cache.countries.get(
                    record.country_name))
                if cs:
                    address.subdivision = cs.get(record.subdivision)
            if 'sequence' in setup.fields:
                address.sequence = record.sequence
            if 'postal_code' in setup.fields:
                address.postal_code = record.postal_code
            if ('contact_value' in setup.fields and record.contact_value and
                    'contact_type' in setup.fields and record.contact_type):
                contact_mechanism = ContactMechanism()
                contact_mechanism.party = cache.parties.get(record.party_code)
                contact_mechanism.type = record.contact_type
                contact_mechanism.value = record.contact_value
                contact_mechanism.address = address
                to_save_contact_mechanism.append((contact_mechanism, record))
            cls.importer_address(record, address)
            to_save.append((address, record))
        cls.importer_save(to_save)
        if to_save_contact_mechanism:
            cls.importer_save(to_save_contact_mechanism)
        return [x[0] for x in to_save]


class ImporterPartyInvoiceDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    invoice_address = fields.Boolean('Invoice Address')


class ImporterPartyStockDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    delivery_address = fields.Boolean('Delivery Address')


class ImporterCustomerDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    customer = fields.Boolean('Customer')


class ImporterSupplierDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    supplier = fields.Boolean('Supplier')


class ImporterPurchaseDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    supplier_lead_time = fields.Integer('Supplier Lead Time (days)')


class ImporterCommissionDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    agent = fields.Char('Agent (code)')


class ImporterAccountDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    customer_tax_rule = fields.Char('Customer Tax Rule')
    supplier_tax_rule = fields.Char('Supplier Tax Rule')
    account_payable = fields.Char('Account Payable')
    account_receivable = fields.Char('Account Receivable')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        setup = Setup.get()
        if ('account_payable' not in setup.fields
                and 'account_receivable' not in setup.fields):
            return
        setup.cache.accounts = Cache('account.account',
            lambda x: (x.company.id, x.code))

    @classmethod
    def import_party_party_hook(cls, record, party):
        super().import_party_party_hook(record, party)
        setup = Setup.get()
        company = Transaction().context.get('company')
        if not company:
            return
        for field in ('account_payable', 'account_receivable'):
            if field not in setup.fields:
                continue
            account_code = getattr(record, field, None)
            if not account_code:
                setattr(party, field, None)
                continue
            setattr(party, field, setup.cache.accounts.get(
                    (company, account_code)))


class ImporterCompanyBankDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    default_payable_bank_account = fields.Char(
        'Default payable bank account')
    default_receivable_bank_account = fields.Char(
        'Default receivable bank account')
    default_payable_company_bank_account = fields.Char(
        'Default payable company  Bank Account')
    default_receivable_company_bank_account = fields.Char(
        'Default receivable company Bank Account')


class ImporterIncotermDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    incoterm_name = fields.Char('Incoterm Name')
    incoterm_place = fields.Char('Incoterm Place')


class ImporterIncotermPurchaseDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    incoterm_purchase_name = fields.Char('Incoterm Purchase Name')
    incoterm_purchase_place = fields.Char('Incoterm Purchase Place')


class ImporterAEATSIIDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    sii_identifier_type = fields.Char('SII Identification Type')


class ImporterCarrierDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    carrier = fields.Char('Carrier')


class ImporterContactMechanism(ImporterModel):
    'Importer Contact Method'
    __name__ = 'importer.party.contact_mechanism'

    party = fields.Char("Party")
    type = fields.Char("Type")
    value = fields.Char("Value")
    name = fields.Char("Name")
    language = fields.Char("Language")
    comment = fields.Char("Comment")

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.parties = Cache('party.party', 'code')
        cache.languages = Cache('ir.lang', 'code')

    @classmethod
    def import_contact_mechanism_hook(cls, record, contact_mechanism):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        ContactMechanismLanguage = pool.get('party.contact_mechanism.language')

        company = Transaction().context.get('company')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        to_save_contact_mechanism_language = []
        for record in records:
            if 'party' in setup.fields:
                party = cache.parties.get(record.party)
                if not party:
                    setup.error(gettext('importer.party_not_found',
                        party=record.party))
                    continue
            contact_mechanism = ContactMechanism()
            contact_mechanism.party = party
            contact_mechanism.name = record.name
            contact_mechanism.type = record.type
            contact_mechanism.value = record.value
            contact_mechanism.comment = record.comment

            cls.import_contact_mechanism_hook(record, contact_mechanism)
            to_save.append((contact_mechanism, record))

            if 'language' in setup.fields and record.language:
                contact_mechanism_language = ContactMechanismLanguage()
                contact_mechanism_language.contact_mechanism = (
                    contact_mechanism)
                contact_mechanism_language.language = cache.languages.get(
                    record.language)
                if not contact_mechanism_language.language:
                    setup.error(gettext('importer.language_not_found',
                        language=record.language))
                    continue
                contact_mechanism_language.company = company
                to_save_contact_mechanism_language.append(
                    (contact_mechanism_language, record))
        cls.importer_save(to_save)
        cls.importer_save(to_save_contact_mechanism_language)
        return [x[0] for x in to_save]


class ImporterContactMechanismInvoiceDepends(metaclass=PoolMeta):
    __name__ = 'importer.party.contact_mechanism'
    invoice = fields.Boolean("Invoice")

    @classmethod
    def import_contact_mechanism_hook(cls, record, contact_mechanism):
        super().import_contact_mechanism_hook(record, contact_mechanism)
        if hasattr(record, 'invoice'):
            contact_mechanism.invoice = record.invoice


class ImporterContactMechanismStockDepends(metaclass=PoolMeta):
    __name__ = 'importer.party.contact_mechanism'
    delivery = fields.Boolean("Delivery")

    @classmethod
    def import_contact_mechanism_hook(cls, record, contact_mechanism):
        super().import_contact_mechanism_hook(record, contact_mechanism)
        if hasattr(record, 'delivery'):
            contact_mechanism.delivery = record.delivery


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'party': {
                    'string': 'Party',
                    'model': 'importer.party',
                    },
                'contact_mechanism': {
                    'string': 'Contact Mechanism',
                    'model': 'importer.party.contact_mechanism',
                    },
                'party_configuration': {
                    'string': 'Party configuration',
                    'model': 'importer.party.configuration',
                    },
                'party_address': {
                    'string': 'Address',
                    'model': 'importer.party.address',
                },
                })
        return methods


class ImporterHolidaysParty(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'party_holidays': {
                    'string': 'Party Holidays',
                    'model': 'importer.party.holidays',
                },
                })
        return methods


class ImpoterPartyHolidays(ImporterModel):
    'Importer Party Holidays'
    __name__ = 'importer.party.holidays'

    party_code = fields.Char('Party Code')
    from_month = fields.Char('From Month')
    from_day = fields.Char('From Day')
    thru_month = fields.Char('Thru Month')
    thru_day = fields.Char('Thru Day')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.parties = Cache('party.party', 'code')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        PartyHolidays = pool.get('party.payment.holidays')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        for record in records:
            if 'party_code' in setup.fields:
                party = cache.parties.get(record.party_code)
                if not party:
                    setup.error(gettext('msg_party_holidays_party_not_found',
                        party=record.party_code))
                    continue
            party_holidays = PartyHolidays()
            party_holidays.party = party
            if 'from_month' in setup.fields:
                from_month = record.from_month
                if len(record.from_month) == 1:
                    from_month = '0' + record.from_month
                party_holidays.from_month = from_month
            if 'from_day' in setup.fields:
                party_holidays.from_day = record.from_day
            if 'thru_month' in setup.fields:
                thru_month = record.thru_month
                if len(record.thru_month) == 1:
                    thru_month = '0' + record.thru_month
                party_holidays.thru_month = thru_month
            if 'thru_day' in setup.fields:
                party_holidays.thru_day = record.thru_day
            to_save.append((party_holidays, record))
        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class ImportFacturaeAddress(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'party_facturae': {
                    'string': 'Party Facutra-e',
                    'model': 'importer.address.facturae',
                },
                })
        return methods


class ImportAddressFacturae(ImporterModel):
    'Importer Address Factura-e'
    __name__ = 'importer.address.facturae'

    party = fields.Char('Party')
    facturae_person_type = fields.Char('Facturae Person Type')
    facturae_residence_type = fields.Char('Facturae Residence Type')
    oficina_contable = fields.Char('Oficina Contable')
    organo_gestor = fields.Char('Organo Gestor')
    unidad_tramitadora = fields.Char('Unidad Tramitadora')

    @classmethod
    def importer_start(cls):
        setup = Setup.get()
        cache = setup.cache
        cache.parties = Cache('party.party', 'code')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Address = pool.get('party.address')
        to_save = []

        setup = Setup.get()
        cache = setup.cache

        for record in records:
            if 'party' in setup.fields:
                party = cache.parties.get(record.party)
                if not party:
                    setup.error(gettext('importer.msg_party_not_found',
                        party=record.party))
                    continue

            if len(party.addresses) == 0:
                address = Address()
                address.party = party
            else:
                address = party.addresses[0]

            if 'facturae_person_type' in setup.fields:
                address.facturae_person_type = record.facturae_person_type
            if 'facturae_residence_type' in setup.fields:
                address.facturae_residence_type = record.facturae_residence_type
            if 'oficina_contable' in setup.fields:
                address.oficina_contable = record.oficina_contable
            if 'organo_gestor' in setup.fields:
                address.organo_gestor = record.organo_gestor
            if 'unidad_tramitadora' in setup.fields:
                address.unidad_tramitadora = record.unidad_tramitadora
            to_save.append((address, record))
        cls.importer_save(to_save)
        return [x[0] for x in to_save]
