from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel


class ImporterPartyCredit(ImporterModel):
    'Importer Party Credit'
    __name__ = 'importer.party.credit'

    party = fields.Char("Party")
    date = fields.DateTime("Date")
    start_date = fields.DateTime("Start Date")
    end_date = fields.DateTime("End Date")
    first_approved_credit_limit = fields.Float("First Approved Credit Limit")
    requested_credit_limit = fields.Float("Requested Credit Limit")

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        Party = pool.get('party.party')

        parties = dict([(x.code, x) for x in Party.search([])])

        to_save = []
        for record in records:
            party_credit = PartyCredit()
            if not parties[record.party]:
                raise
            party_credit.party = parties[record.party]
            party_credit.date = record.date
            party_credit.start_date = record.start_date
            party_credit.end_date = record.end_date
            party_credit.first_approved_credit_limit = (
                record.first_approved_credit_limit)
            party_credit.requested_credit_limit = (
                record.requested_credit_limit)
            to_save.append(party_credit)

        PartyCredit.save(to_save)
        return to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'party_credit': {
                    'string': 'Party Credit',
                    'model': 'importer.party.credit',
                    },
                })
        return methods
