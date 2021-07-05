from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from decimal import Decimal
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterAccountMove(ModelView):
    'Importer AccountMove'
    __name__ = 'importer.account.move'

    number = fields.Char('Move Number')
    journal_code = fields.Char('Journal Code')
    effective_date = fields.Date('Effecive Date')
    account_code = fields.Char('Account Code')
    party_code = fields.Char('Party Code')
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
        })
        return methods

    @classmethod
    def import_account_move_header(cls, record):
        return record.number

    @classmethod
    def get_party_dict(cls):
        Party = Pool().get('party.party')
        return dict((x.code, x) for x in Party.search([]))

    def import_account_move(cls, records):
        pool = Pool()
        Account = pool.get('account.account')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        accounts = dict((x.code, x) for x in Account.search([]))
        clients = cls.get_party_dict()
        journals = dict((x.code, x) for x in Journal.search([]))
        periods = {}

        moves_to_save = []
        previous_header = None
        for record in records:
            header = cls.import_account_move_header(record)
            account = accounts.get(record.account_code, None)
            if not account:
                raise UserError(gettext('importer.account_not_found',
                        account=record.account_code))

            if header and header != previous_header:
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
                    periods[date] = period[0]
                move = Move(**values)
                move.number = record.number
                move.date = date
                move.period = period
                move.journal = journals.get(record.journal_code)
                move.lines = []
                moves_to_save.append(move)

            party = clients.get(record.party_code)
            if account.party_required and not party:
                raise UserError(gettext('importer.party_required_for_account',
                        account=record.account_code, move=move.number))

            line = Line()
            line.account = account
            line.description = record.description
            line.debit = Decimal("%.2f" % (record.debit or 0))
            line.credit = Decimal("%.2f" % (record.credit or 0))
            line.party = party

            move.lines += (line, )
        Move.save(moves_to_save)
        return moves_to_save
