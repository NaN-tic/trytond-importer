from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from decimal import Decimal
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.transaction import Transaction


class ImporterAccountMove(ModelView):
    'Importer AccountMove'
    __name__ = 'importer.account.move'

    number = fields.Char('Move Number')
    journal_code = fields.Char('Journal Code')
    effective_date = fields.Date('Effecive Date')
    account_code = fields.Char('Account Code')
    account_name = fields.Char('Account Name')
    party_code = fields.Char('Party Code')
    party_name = fields.Char('Party Name')
    debit = fields.Float('Debit')
    credit = fields.Float('Credit')
    description = fields.Char('Description')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
            'account_move': {
                'string': 'Account Move',
                'model': 'importer.account.move',
                'chunked': False,
            },
            'account_move_party': {
                'string': 'Account Move Create Missing Party',
                'model': 'importer.account.move',
                'chunked': False,
            },
            'account_move_account': {
                'string': 'Account Move Create Missing Account',
                'model': 'importer.account.move',
                'chunked': False,
            },
            'account_move_account_party': {
                'string': 'Account Move Create Missing Account and Party',
                'model': 'importer.account.move',
                'chunked': False,
            },
        })
        return methods

    @classmethod
    def import_account_move_header(cls, record):
        return (record.number, record.effective_date)


    @classmethod
    def get_party_dict(cls):
        Party = Pool().get('party.party')
        return dict((x.code, x) for x in Party.search([]))

    def import_account_move(cls, records):
        return cls._import_account_move(records)

    def import_account_move_party(cls, records):
        return cls._import_account_move(records, create_party=True)

    def import_account_move_account(cls, records):
        return cls._import_account_move(records, create_account=True)

    def import_account_move_account_party(cls, records):
        return cls._import_account_move(records, create_party=True,
            create_account=True)

    def _import_account_move(cls, records, create_party=False,
            create_account=False):
        pool = Pool()
        Account = pool.get('account.account')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Party = Pool().get('party.party')
        PartyIdentifier = Pool().get('party.identifier')

        def _create_party(code, name):
            party = Party(name=name, code=code)
            party.identifiers = [PartyIdentifier(code=code, type=None)]
            return party

        accounts = dict((x.code, x) for x in Account.search([]))
        clients = cls.get_party_dict()
        journals = dict((x.code, x) for x in Journal.search([]))
        periods = {}

        chart = {}
        if create_account:
            company = Transaction().context.get('company')
            chart = cls.get_chart_tree(company)

        moves_to_save = []
        previous_header = None
        accounts_to_save = []
        party_to_save = []
        for record in records:
            if record.account_code is None:
                continue
            header = cls.import_account_move_header(record)
            account = accounts.get(record.account_code, None)
            if not account:
                if create_account:
                    account = cls.create_account(record.account_code,
                        record.account_name, chart)
                if not account:
                    raise UserError(gettext('importer.account_not_found',
                        account=record.account_code))
                accounts_to_save.append(account)
                accounts[account.code] = account

            if any(header) and header != previous_header:
                previous_header = header
                values = Move.default_get(list(Move._fields.keys()),
                    with_rec_name=False)

                date = record.effective_date
                period = periods.get(date)
                if not period:
                    period = Period.search([
                            ('start_date', '<=', date),
                            ('end_date', '>=', date),
                            ('type', '=', 'standard'),
                            ], limit=1)
                    if not period:
                        raise UserError(gettext('importer.no_period_for_date',
                                date=date.strftime('%Y-%m-%d')))
                    period = period[0]
                    periods[date] = period
                move = Move(**values)
                move.date = date
                move.post_number = record.number
                move.period = period
                move.journal = journals.get(record.journal_code)
                move.lines = []
                moves_to_save.append(move)

            party = clients.get(record.party_code)
            if account.party_required and not party:
                if not create_party:
                    raise UserError(gettext(
                        'importer.party_required_for_account',
                        account=record.account_code, move=record.number))
                party = _create_party(record.party_code, record.party_name)
                clients[party.code] = party
                party_to_save.append(party)

            line = Line()
            line.account = account
            line.description = record.description
            line.debit = Decimal("%.2f" % (record.debit or 0))
            line.credit = Decimal("%.2f" % (record.credit or 0))
            line.party = party

            move.lines += (line, )

        if party_to_save:
            Party.save(party_to_save)
        if accounts_to_save:
            Account.save(accounts_to_save)

        offset = 100
        i = 0
        while i < len(moves_to_save):
            m = moves_to_save[i:min(i+offset, len(moves_to_save))]
            i += offset
            Move.save(m)
        return moves_to_save

    def create_account(self, code, name, chart):
        Configurator = Pool().get('account.configuration')
        config = Configurator(1)

        code = self.get_code(code)
        existing = chart.get(code)
        if existing:
            return
        digits = config.default_account_code_digits or 8
        similar_account = self.get_similar_account(code, chart, digits)
        account = self.similar_account(similar_account, {'code': code,
            'name': name})
        account.code =code
        account.name = name
        chart[code] = account
        return account

    def get_similar_account(self, code, chart, digits=8):
        if len(code) < digits:
            for digits in (4, 3, 2, 1):
                code2 = code[:digits]
                account = chart.get(code2)
                if account:
                    break

        if len(code) == digits:
            # Ensure that we find a valid account
            for i in range(len(code)):
                sub_code = code[:-i].ljust(digits, '0')
                if sub_code in chart:
                    new_account = chart.get(sub_code)
                    if new_account.type != None:
                        account = new_account
                        break

        if account:
            return account

    def similar_account(self, sim_account, vals):
        Account = Pool().get('account.account')
        account = Account()

        ignore_fields = ['id', 'code', 'name', 'childs', 'deferrals', 'taxes',
            'create_date', 'create_uid', 'write_date', 'write_uid', 'template',
            'parent', 'company', 'general_ledger_balance', 'balance', 'credit',
            'debit', 'right', 'left']

        for field in Account._fields:
            if field in ignore_fields:
                continue
            value = getattr(sim_account, field)
            setattr(account, field, value)

        if (sim_account.code and sim_account.parent and
                len(vals.get('code', '')) == len(sim_account.code)):
            account.parent = sim_account.parent
        else:
            account.parent = sim_account

        for k, v in vals.items():
            setattr(account, k, v)

        return account

    def get_account_party_codes(self):
        Account = Pool().get('account.account')
        accounts = Account.search([('party_required', '=', True)])
        return [x.code[0:4] for x in accounts]

    def get_code(self, code, digits=8):
        if len(code) > 4:
            if code[:4] in self.get_account_party_codes():
                return code[0:4].ljust(len(code), '0')
        return code

    def get_chart_tree(self, company):
        Account = Pool().get('account.account')
        accounts = Account.search([('company', '=', company)])
        return dict((str(a.code), a) for a in accounts)
