from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from .tools import ImporterModel


class ImporterCandidate(ImporterModel):
    'Importer Candidate'
    __name__ = 'importer.candidate'

    party_name = fields.Char("Party Name")
    phone = fields.Char("Phone")
    email = fields.Char("E-mail")
    profile_url = fields.Char("Profile URL")
    vacancy = fields.Char("Vacancy")
    phase = fields.Char('Phase')
    application_method = fields.Char('Application Method')
    application_url = fields.Char('Application URL')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ApplicationMethod = pool.get('employee.candidate.application_method')
        Candidate = pool.get('employee.candidate')
        ContactMechanism = pool.get('party.contact_mechanism')
        Party = pool.get('party.party')
        Resume = pool.get('employee.resume')
        Phase = pool.get('employee.candidate.phase')
        Vacancy = pool.get('employee.vacancy')

        vacancies = {x.name: x for x in Vacancy.search([])}
        methods = {x.name: x for x in ApplicationMethod.search([])}
        phases = {x.name: x for x in Phase.search([])}

        candidates = []
        for record in records:
            party = Party()
            party.name = record.party_name
            party.save()
            phone = ContactMechanism()
            phone.party = party
            phone.type = 'phone'
            phone.value = record.phone
            phone.save()
            email = ContactMechanism()
            email.party = party
            email.type = 'email'
            email.value = record.email
            email.save()
            resume = Resume()
            resume.party = party
            resume.url = record.profile_url
            resume.save()
            candidate = Candidate()
            candidate.vacancy = vacancies.get(record.vacancy)
            candidate.party = party
            candidate.phase = phases.get(record.phase)
            candidate.application_method = methods.get(record.application_method)
            candidate.url = record.application_url
            candidate.save()
            candidates.append(candidate)
        return candidates


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'candidate': {
                    'string': 'Candidate',
                    'model': 'importer.candidate',
                    },
                })
        return methods
