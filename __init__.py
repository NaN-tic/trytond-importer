    Pool.register(
        account.Importer,
        account.ImporterAccountAsset,
        account.ImporterAccountMove,
        account.ImporterChart,
        account.ImporterFiscalYear,
        account.ImporterAccountJournal,
        party.ImporterAccountDepends,
        depends=['account'],
        module='importer', type_='model')
