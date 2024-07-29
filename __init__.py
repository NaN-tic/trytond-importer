# This file is part importer module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import agronomics
from . import account
from . import bank
from . import bank_es
from . import company
from . import country
from . import crop
from . import currency
from . import farm
from . import invoice
from . import ir
from . import importer
from . import lot
from . import marketing
from . import meta
from . import order_point
from . import party
from . import party_credit
from . import price_list
from . import product
from . import production
from . import purchase
from . import sale
from . import sale_discount
from . import discount_formula
from . import stock
from . import res
from . import route
from . import user_role
from . import vacancy

def register():
    Pool.register(
        importer.Importer,
        importer.ImporterColumn,
        importer.ImporterSourceColumn,
        importer.ImporterError,
        importer.ImportAsk,
        ir.Importer,
        ir.ImporterLanguage,
        ir.ImporterSequence,
        res.Importer,
        res.ImporterUser,
        meta.Importer,
        meta.ImporterMeta,
        module='importer', type_='model')
    Pool.register(
        importer.AskAndImport,
        importer.Import,
        module='importer', type_='wizard')
    Pool.register(
        importer.ExcelTemplate,
        module='importer', type_='report')
    Pool.register(
        party_credit.ImporterPartyCredit,
        party_credit.Importer,
        depends=['account_insurance_credit_limit'],
        module='importer', type_='model')
    Pool.register(
        party.Importer,
        party.ImporterParty,
        party.ImporterPartyConfiguration,
        party.ImporterContactMechanism,
        depends=['party'],
        module='importer', type_='model')
    Pool.register(
        product.Importer,
        product.ImporterProduct,
        product.ImporterProductCodes,
        product.ImporterProductConfiguration,
        depends=['product'],
        module='importer', type_='model')
    Pool.register(
        price_list.Importer,
        price_list.ImporterPriceList,
        depends=['product_price_list'],
        module='importer', type_='model')
    Pool.register(
        sale.Importer,
        sale.ImporterSale,
        sale.ImporterSaleConfiguration,
        depends=['sale'],
        module='importer', type_='model')
    Pool.register(
        sale_discount.Importer,
        sale_discount.ImporterSale,
        depends=['sale_discount'],
        module='importer', type_='model')
    Pool.register(
        discount_formula.Importer,
        discount_formula.ImporterSale,
        depends=['sale_discount', 'discount_formula'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterPurchaseDepends,
        purchase.Importer,
        purchase.ImporterPurchase,
        purchase.ImporterProductSupplier,
        purchase.ImporterPurchaseConfiguration,
        depends=['purchase'],
        module='importer', type_='model')
    Pool.register(
        discount_formula.ImporterProductSupplier,
        depends=['purchase', 'discount_formula'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterPartyStockDepends,
        party.ImporterContactMechanismStockDepends,
        stock.Importer,
        stock.ImporterLocation,
        stock.ImporterStockMove,
        depends=['stock'],
        module='importer', type_='model')
    Pool.register(
        lot.Importer,
        lot.ImporterLot,
        depends=['stock_lot'],
        module='importer', type_='model')
    Pool.register(
        account.Importer,
        account.ImporterAccountMove,
        account.ImporterChart,
        account.ImporterFiscalYear,
        party.ImporterAccountDepends,
        depends=['account'],
        module='importer', type_='model')
    Pool.register(
        account.ImporterAccountMoveDependsAnalytic,
        depends=['analytic_account'],
        module='importer', type_='model')
    Pool.register(
        farm.Importer,
        farm.ImporterFarmMoveEvent,
        farm.ImporterFarmRemovalEvent,
        farm.ImporterFarmAnimal,
        farm.ImporterFarmMedicationEvent,
        farm.ImporterFarmInseminationEvent,
        farm.ImporterFarmPregnancyDiagnosisEvent,
        farm.ImporterFarmAbortEvent,
        farm.ImporterFarmFarrowingEvent,
        farm.ImporterFarmWeaningEvent,
        farm.ImporterFarmTransformationEvent,
        farm.ImporterFarmReclassificationEvent,
        depends=['farm'],
        module='importer', type_='model')
    Pool.register(
        crop.Importer,
        crop.ImporterParcel,
        crop.ImporterPlantation,
        depends=['agronomics'],
        module='importer', type_='model')
    Pool.register(
        invoice.Importer,
        invoice.ImporterInvoice,
        party.ImporterPartyInvoiceDepends,
        party.ImporterContactMechanismInvoiceDepends,
        depends=['account_invoice'],
        module='importer', type_='model')
    Pool.register(
        agronomics.Importer,
        agronomics.ImporterProductAgronomics,
        depends=['agronomics'],
        module='importer', type_='model')
    Pool.register(
        order_point.Importer,
        order_point.ImporterOrderPoint,
        depends=['stock_supply'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductStockProductLocationDepends,
        depends=['stock_product_location'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductSupplierMinimumDepends,
        purchase.ImporterProductSupplierStockSupplyMinimum,
        depends=['stock_supply_minimum'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductSupplierMultipleDepends,
        purchase.ImporterProductSupplierStockSupplyMultiple,
        depends=['stock_supply_multiple'],
        module='importer', type_='model')
    Pool.register(
        purchase.ImporterProductSupplierPurchaseSupplierPricePeriod,
        depends=['purchase_supplier_price_period'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterCustomerDepends,
        depends=['party_customer'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterSupplierDepends,
        depends=['party_supplier'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterCommissionDepends,
        depends=['commission'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterIncotermDepends,
        depends=['incoterm'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterIncotermPurchaseDepends,
        depends=['purchase_incoterm'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterAEATSIIDepends,
        depends=['aeat_sii'],
        module='importer', type_='model')
    Pool.register(
        party.ImporterCompanyBankDepends,
        depends=['company_bank'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductProductionDepends,
        production.Importer,
        production.ImporterProductionBom,
        production.ImporterProductionConfiguration,
        depends=['production'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductProductMeasuresDepends,
        depends=['product_measurements'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductPackagesDepends,
        depends=['product_package'],
        module='importer', type_='model')
    Pool.register(
        route.ImporterRoute,
        route.Importer,
        depends=['production_route'],
        module='importer', type_='model')
    Pool.register(
        product.ImporterProductProductionRouteDepends,
        depends=['production_route'],
        module='importer', type_='model')
    Pool.register(
        vacancy.ImporterCandidate,
        vacancy.Importer,
        depends=['employee_vacancy'],
        module='importer', type_='model')
    Pool.register(
        currency.Importer,
        currency.ImporterCurrency,
        depends=['currency'],
        module='importer', type_='model')
    Pool.register(
        company.Importer,
        company.ImporterCompany,
        company.ImporterEmployee,
        depends=['company'],
        module='importer', type_='model')
    Pool.register(
        country.Importer,
        country.ImporterCountry,
        country.ImporterPostalCodes,
        depends=['country'],
        module='importer', type_='model')
    Pool.register(
        marketing.Importer,
        marketing.ImporterMarketingEmail,
        depends=['marketing_email'],
        module='importer', type_='model')
    Pool.register(
        user_role.Importer,
        user_role.ImporterRole,
        depends=['user_role'],
        module='importer', type_='model')
    Pool.register(
        bank.Importer,
        bank.ImporterBank,
        depends=['bank'],
        module='importer', type_='model')
    Pool.register(
        bank_es.Importer,
        bank_es.ImporterSpanishBank,
        depends=['bank_es'],
        module='importer', type_='model')

