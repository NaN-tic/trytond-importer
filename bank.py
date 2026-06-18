from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from .tools import ImporterModel, Cache, Setup
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterBank(ImporterModel):
    'Importer Bank'
    __name__ = 'importer.bank'
    name = fields.Char('Name')
    bic = fields.Char('BIC')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Bank = pool.get('bank')

        to_save = []
        for record in records:
            if not record.name:
                raise UserError(gettext('importer.msg_bank_name_required'))
            banks = Bank.search([('party.name', '=', record.name)], limit=1)
            if banks:
                bank, = banks
            else:
                parties = Party.search([('name', '=', record.name)], limit=1)
                if parties:
                    party, = parties
                else:
                    party = Party()
                    party.name = record.name
                    party.save()
                bank = Bank()
                bank.party = party

            bank.bic = record.bic
            to_save.append(bank)

        Bank.save(to_save)
        return to_save


class ImporterBankAccount(ImporterModel):
    'Importer Bank Account'
    __name__ = 'importer.bank.account'

    iban = fields.Char('IBAN')
    owner_codes = fields.Char('Owner Codes')
    owner_names = fields.Char('Owner Names')

    @classmethod
    def importer_start(cls):
        super().importer_start()

        cache = Setup.get().cache
        cache.bank_accounts = Cache('bank.account.number', 'number_compact',
            required=False)
        cache.parties = Cache('party.party', 'code', required=False, context={
                'active_test': False,
                })

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        BankAccount = pool.get('bank.account')
        AccountNumber = pool.get('bank.account.number')

        setup = Setup.get()
        cache = setup.cache
        to_save = []

        def get_owner_by_code(code):
            owner = cache.parties.get(code)
            if owner:
                return owner
            setup.error(gettext('importer.party_not_found', party=code))

        def get_owner_by_name(name):
            with Transaction().set_context(active_test=False):
                owners = Party.search([('name', '=', name)])
            if len(owners) == 1:
                return owners[0]
            if len(owners) > 1:
                setup.error(gettext('importer.single_party_error', party=name))
            else:
                setup.error(gettext('importer.party_not_found', party=name))

        for record in records:
            setup.current_record = record
            owners = []

            if record.owner_codes:
                for code in record.owner_codes.split('|'):
                    code = code.strip()
                    if not code:
                        continue
                    owner = get_owner_by_code(code)
                    if owner and owner not in owners:
                        owners.append(owner)

            if record.owner_names:
                for name in record.owner_names.split('|'):
                    name = name.strip()
                    if not name:
                        continue
                    owner = get_owner_by_name(name)
                    if owner and owner not in owners:
                        owners.append(owner)

            if record.iban:
                for iban in record.iban.split('|'):
                    iban = iban.replace(' ', '')
                    if not iban:
                        continue
                    if len(iban) < 8:
                        setup.error(gettext('importer.msg_wrong_iban',
                            iban=iban))
                        continue

                    bank_number = cache.bank_accounts.get(iban)
                    if bank_number:
                        bank_account = bank_number.account
                    else:
                        bank_account = BankAccount()
                        account_number = AccountNumber()
                        account_number.account = bank_account
                        account_number.type = 'iban'
                        account_number.number = iban
                        bank_account.numbers = [account_number]
                        bank_account.owners = []
                        cache.bank_accounts[iban] = account_number

                    current_owners = list(bank_account.owners or ())
                    for owner in owners:
                        if owner not in current_owners:
                            current_owners.append(owner)
                    bank_account.owners = current_owners

                    if bank_account not in [x[0] for x in to_save]:
                        to_save.append((bank_account, record))

        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'bank': {
                    'string': 'Banks',
                    'model': 'importer.bank',
                    },
                'bank_account': {
                    'string': 'Bank Accounts',
                    'model': 'importer.bank.account',
                    },
                })
        return methods
