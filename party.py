from datetime import timedelta
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from stdnum import get_cc_module
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterPartyConfiguration(ModelView):
    'Importer Party Configuration'
    __name__ = 'importer.party.configuration'

    language_code = fields.Char('Language Code')
    sequence_prefix = fields.Char("Sequence prefix")
    sequence_suffix = fields.Char("Sequence suffix")
    sequence_padding = fields.Integer("Sequence Padding")
    sequence_number_next = fields.Integer("Sequence Number Next")


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

class ImporterCompanyBankDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
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


class ImporterContactMechanism(ModelView):
    'Importer Contact Method'
    __name__ = 'importer.party.contact_mechanism'

    party = fields.Char("Party")
    type = fields.Char("Type")
    value = fields.Char("Value")
    name = fields.Char("Name")
    language = fields.Char("Language")


class ImporterContactMechanismInvoiceDepends(metaclass=PoolMeta):
    __name__ = 'importer.party.contact_mechanism'

    invoice = fields.Boolean("Invoice")


class ImporterContactMechanismStockDepends(metaclass=PoolMeta):
    __name__ = 'importer.party.contact_mechanism'

    delivery = fields.Boolean("Delivery")

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
                'contact_mechanism': {
                    'string': 'Contact Mechanism',
                    'model': 'importer.party.contact_mechanism',
                    'chunked': True,
                    },
                'party_configuration': {
                    'string': 'Party configuration',
                    'model': 'importer.party.configuration',
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
            bank_accounts = dict((x.number_compact, x) for x in
                    AccountNumber.search([]))
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

        try:
            TaxRule = pool.get('account.tax.rule')
            tax_rules = dict([(x.name, x) for x in TaxRule.search([])])
        except:
            pass

        try:
            Agent = pool.get('commission.agent')
            agents = dict([((x.party.code, x.plan.name), x)
                    for x in Agent.search([])])
        except:
            pass

        try:
            Incoterm = pool.get('incoterm')
            incoterms = dict([(x.code, x) for x in Incoterm.search([])])
        except:
            pass


        company = Transaction().context.get('company')

        languages = dict([(x.code, x) for x in Lang.search([])])
        categories = dict([(x.name, x) for x in PartyCategory.search([])])
        countries = dict([(x.code, x) for x in Country.search([])])
        subdivisions = dict([(x.name, x) for x in Subdivision.search([])])
        parties = dict([(x.code, x) for x in Party.search([])])

        vats = {}
        to_save = []
        relations_to_save = {}
        for record in records:
            party = Party()
            to_save.append(party)

            parties[record.code] = party
            party.name = record.name
            party.code = record.code
            if 'trade_name' in party._fields:
                party.trade_name = record.trade_name

            if hasattr(Party, 'supplier'):
                party.supplier = record.supplier

            if hasattr(Party, 'customer'):
                party.customer = record.customer

            # TODO allow days, hours... cast_value format
            if (hasattr(Party, 'supplier_lead_time') and
                        record.supplier_lead_time):
                party.supplier_lead_time = timedelta(
                    days=record.supplier_lead_time)

            addresses = []
            address = Address()
            address.street = record.street
            address.postal_code = record.postal_code
            address.city = record.city
            country = countries.get(record.country)
            address.country = country
            if hasattr(Address, 'delivery'):
                address.delivery = record.delivery_address
            if hasattr(Address, 'invoice'):
                address.invoice = record.invoice_address
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
                    'supplier_payment_days' in party._fields):
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

            if hasattr(Party, 'customer_tax_rule'):
                party.customer_tax_rule = tax_rules.get(
                    record.customer_tax_rule)
                party.supplier_tax_rule = tax_rules.get(
                    record.supplier_tax_rule)

            if record.bank_account and 'bank_accounts' in party._fields:
                Currency = pool.get('currency.currency')
                currencies = dict([(x.code, x) for x in Currency.search([])])
                party.bank_accounts = []
                for account in record.bank_account.split('|'):
                    if (',') in account:
                        iban, currency_code = account.split(',')
                    else:
                        iban = account
                        currency_code = 'EUR'
                    iban = iban.replace(" ", "")
                    currency = currencies.get(currency_code)
                    if len(iban) < 8:
                        raise UserError(gettext('importer.wron_iban',
                            iban_= iban))

                    bank_code = iban[4:8]
                    bank = banks.get(bank_code)
                    if not bank:
                        raise UserError(gettext('importer.bank_not_found',
                            iban=iban))
                    bank_account = BankAccount()
                    bank_account.bank = bank
                    bank_account.currency = currency
                    account_number = AccountNumber()
                    account_number.account = bank_account
                    account_number.type = 'iban'
                    account_number.number = iban
                    bank_accounts[iban]=account_number
                    bank_account.numbers = [account_number]
                    party.bank_accounts += (bank_account,)
                party.payable_bank_account = party.bank_accounts[0]
                party.receivable_bank_account = party.bank_accounts[0]


            if hasattr(Party, 'bank_accounts'):
                company_pay_bank_acc = bank_accounts.get(
                    record.default_payable_company_bank_account)
                company_rec_bank_acc = bank_accounts.get(
                    record.default_receivable_company_bank_account)
                if company_pay_bank_acc:
                    party.payable_company_bank_account = company_pay_bank_acc.account
                if company_rec_bank_acc:
                    party.receivable_company_bank_account = company_rec_bank_acc.account

            if hasattr(Party, 'agents') and record.agent:
                new_agents = []
                CommisionAgentSelection = pool.get('commission.agent.selection')
                for agent in record.agent.split('|'):
                    agent, plan = agent.split(',')
                    com_agen_sel = CommisionAgentSelection()
                    key = (agent, plan)
                    com_a = agents.get((key))
                    if not com_a:
                        raise UserError(gettext('importer.agent_not_found',
                            agent=agent, plan=plan))
                    com_agen_sel.agent = com_a
                    com_agen_sel.company = company
                    new_agents.append(com_agen_sel)
                party.agents = new_agents


            if hasattr(Party, 'sii_identifier_type'):
                if record.sii_identifier_type != 'None':
                    party.sii_identifier_type = record.sii_identifier_type

            if hasattr(Party, 'incoterm'):
                party.incoterm = incoterms.get(record.incoterm_name)
                party.on_change_incoterm()
                party.incoterm_place = record.incoterm_place
            if hasattr(Party, 'purchase_incoterm'):
                party.purchase_incoterm = incoterms.get(
                    record.incoterm_purchase_name)
                party.on_change_purchase_incoterm()
                party.purchase_incoterm_place = record.incoterm_purchase_place

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

    @classmethod
    def import_contact_mechanism(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Lang = pool.get('ir.lang')
        ContactMechanism = pool.get('party.contact_mechanism')
        ContactMechanismLanguage = pool.get('party.contact_mechanism.language')

        company = Transaction().context.get('company')
        languages = dict([(x.code, x) for x in Lang.search([])])
        parties = dict([(x.code, x) for x in Party.search([])])

        to_save_cm = []
        to_save_cml = []
        for record in records:
            if not record.party in parties:
                raise UserError(
                    gettext('importer.party_not_found',
                        party=record.party))
            cm = ContactMechanism()
            cm.party = parties[record.party]
            cm.name = record.name
            cm.type = record.type
            cm.value = record.value

            if hasattr(ContactMechanism, 'invoice'):
                cm.invoice = False
                if record.invoice:
                    cm.invoice = record.invoice

            if hasattr(ContactMechanism, 'delivery'):
                cm.delivery = False
                if record.delivery:
                    cm.delivery = record.delivery

            to_save_cm.append(cm)
            if record.language:
                cml = ContactMechanismLanguage()
                cml.contact_mechanism = cm
                cml.language = languages.get(record.language)
                cml.company = company
                to_save_cml.append(cml)

        ContactMechanism.save(to_save_cm)
        ContactMechanismLanguage.save(to_save_cml)
        return to_save_cm

    @classmethod
    def import_party_configuration(cls, records):
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

                sequence.sequence_type = ModelData.get_id('party', 'sequence_type_party')
                sequence.prefix = record.sequence_prefix
                sequence.suffix = record.sequence_suffix
                sequence.padding = record.sequence_padding
                sequence.number_next = record.sequence_number_next
                sequence.save()

            langs = Lang.search(["code", "=", record.language_code], limit=1)
            if langs:
                configuration.party_lang, = langs
                configuration.save()

            to_save.append(configuration)

        Configuration.save(to_save)

        return to_save