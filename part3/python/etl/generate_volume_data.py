# Jingrui Feng (jf4446) - database systems project part 3 - synthetic transaction data generator
"""Generate reproducible Part 3 transactional CSVs. Seed: 20260727.

Term products are the five Product rows whose LineOfBusiness is ``Term Life``;
they expire after their Duration (10 or 20 years). Whole Life and Universal
Life products have no ExpiryDate. Contract EffectiveDate is the simplified
application/issue/effective date used throughout this project.

Renewal discount formula: for a contract with an enrollment, take the mean of
positive ImprovementPct values from its RISK_IMPROVEMENT rows dated strictly
before the renewal date, rounded to two decimals and capped at 15.00. A
contract without qualifying rows receives 0.00. RATE is intentionally empty,
so Contract and POLICY_RENEWAL premium amounts are synthetic historical values.
"""
from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median


SEED = 20260727
ROW_COUNTS = {
    "Customer": 50_000, "Product": 15, "BillingAccount": 40_000,
    "RATE_VERSION": 6, "Contract": 60_000, "ContractParty": 90_000,
    "Claim": 5_000, "Invoice": 300_000, "WELLNESS_PROGRAM": 5,
    "WELLNESS_ENROLLMENT": 24_000, "WELLNESS_ACTIVITY": 1_000_000,
    "RISK_IMPROVEMENT": 48_000, "POLICY_RENEWAL": 90_000,
    "Account": 40_000, "AccountMember": 50_000, "Relation_3": 40_000,
    "APPLICATION": 90_000,
}
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "synthetic" / "large"
STAGING_BRFSS = ROOT / "data" / "processed" / "staging_load" / "STG_BRFSS_RECORD.csv"
WINDOW_START, AS_OF = date(2021, 1, 1), date(2026, 7, 1)
YEAR_WEIGHTS = [14, 16, 18, 20, 22, 24]  # 2021 through 2026; growing book.


def iso(value: date | None) -> str:
    return "" if value is None else value.isoformat()


def money(value: float) -> str:
    return f"{value:.2f}"


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def weighted_date(rng: random.Random) -> date:
    year = rng.choices(range(2021, 2027), weights=YEAR_WEIGHTS, k=1)[0]
    start = date(year, 1, 1)
    end = AS_OF if year == 2026 else date(year, 12, 31)
    return start + timedelta(days=rng.randrange((end - start).days + 1))


def late_date(rng: random.Random, start: date, end: date) -> date:
    """Date in inclusive interval, biased toward the later endpoint."""
    assert start <= end
    return start + timedelta(days=int((end - start).days * (rng.random() ** 0.55)))


def active_rate_version(value: date) -> int:
    return min(6, max(1, value.year - 2020))


def age_at(dob: date, on_date: date) -> int:
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))


def age_band_for(age: int) -> str:
    if 18 <= age <= 24:
        return "18-24"
    if 25 <= age <= 29:
        return "25-29"
    if 30 <= age <= 34:
        return "30-34"
    if 35 <= age <= 39:
        return "35-39"
    if 40 <= age <= 44:
        return "40-44"
    if 45 <= age <= 49:
        return "45-49"
    if 50 <= age <= 54:
        return "50-54"
    if 55 <= age <= 59:
        return "55-59"
    if 60 <= age <= 64:
        return "60-64"
    if 65 <= age <= 69:
        return "65-69"
    if 70 <= age <= 74:
        return "70-74"
    if 75 <= age <= 79:
        return "75-79"
    if 80 <= age <= 99:
        return "80-99"
    raise ValueError(f"Applicant age has no supported BRFSS band: {age}")


def bmi_band_for(value: float) -> str:
    """Match the BRFSS BMI-category boundaries preserved in staging."""
    if value < 18.5:
        return "under"
    if value < 25:
        return "normal"
    if value < 30:
        return "over"
    return "obese"


def write_csv(table: str, headers: list[str], rows) -> int:
    path = OUT / f"{table}.csv"
    print(f"{table}: writing {ROW_COUNTS[table]:,} rows")
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
            count += 1
            if table == "WELLNESS_ACTIVITY" and count % 100_000 == 0:
                print(f"  {table}: {count:,}/{ROW_COUNTS[table]:,}")
    assert count == ROW_COUNTS[table], (table, count)
    return count


PRODUCTS = [
    ("Term Life", "T100", "Standard", "Level Term 10", "L10", 10, 720.00),
    ("Term Life", "T100", "Preferred", "Level Term 10", "L10P", 10, 560.00),
    ("Term Life", "T200", "Standard", "Level Term 20", "L20", 20, 940.00),
    ("Term Life", "T200", "Preferred", "Level Term 20", "L20P", 20, 745.00),
    ("Term Life", "T300", "Family", "Family Term 20", "FT20", 20, 1_180.00),
    ("Whole Life", "W100", "Standard", "Whole Life Base", "WL1", 0, 1_540.00),
    ("Whole Life", "W100", "Preferred", "Whole Life Base", "WL1P", 0, 1_225.00),
    ("Whole Life", "W200", "Estate", "Estate Whole Life", "EWL", 0, 2_200.00),
    ("Whole Life", "W300", "Family", "Family Whole Life", "FWL", 0, 1_860.00),
    ("Whole Life", "W400", "Legacy", "Legacy Whole Life", "LWL", 0, 2_750.00),
    ("Universal Life", "U100", "Standard", "Flexible Universal", "UL1", 0, 1_020.00),
    ("Universal Life", "U100", "Preferred", "Flexible Universal", "UL1P", 0, 830.00),
    ("Universal Life", "U200", "Estate", "Estate Universal", "EUL", 0, 1_970.00),
    ("Universal Life", "U300", "Family", "Family Universal", "FUL", 0, 1_420.00),
    ("Universal Life", "U400", "Legacy", "Legacy Universal", "LUL", 0, 2_360.00),
]


def build_customers(rng: random.Random):
    records = []
    headers = ["CustLastName", "CustFirstName", "CustMiddleInitial", "CustSuffix", "CustDOB", "CustSalutation", "CusteMailAddress", "Gender", "SSN_TIN", "SSNType", "CustomerLegacyID", "WithholdingCode", "PreferredLanguage", "StartDate", "EndDate", "CustomerID"]
    rows = []
    for i in range(1, ROW_COUNTS["Customer"] + 1):
        first, last = f"First{i:05d}", f"Last{i:05d}"
        dob = date(1940 + (i % 62), 1 + (i % 12), 1 + (i % 28))
        start = weighted_date(rng)
        records.append((last, first, chr(65 + i % 26), "NA", dob))
        ssn = f"{i % 1_000_000_000:09d}"
        rows.append([last, first, chr(65 + i % 26), "NA", iso(dob), "Mx", f"c{i:05d}@example.com", "F" if i % 2 else "M", f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}", "SSN", f"LEG{i:06d}", "EX", "English", iso(start), "", i])
    write_csv("Customer", headers, rows)
    return records


def build_products():
    headers = ["LineOfBusiness", "SeriesName", "PlanName", "RiderName", "PlanCode", "RatebookLocationCode", "Description", "Benefit", "AnnualizedPremium", "ProductID"]
    rows = []
    for i, (lob, series, plan, description, code, duration, premium) in enumerate(PRODUCTS, 1):
        rows.append([lob, series, plan, "Base", code, "RB-EAST", description, f"{duration or 'Lifetime'} year benefit", money(premium), i])
    assert len({(r[0], r[1], r[2]) for r in rows}) == len(rows)
    write_csv("Product", headers, rows)


def build_billing_accounts(rng: random.Random):
    headers = ["BAcctName", "BAcctName2", "BillingAddress1", "BillingAddress2", "BillingCity", "BillingState", "BillingZip", "GroupNumber", "TaxIDNumber", "GeoCode", "OnlineBillingFlag", "ActivityStatus", "BillingPhone", "BillingAccountID"]
    states = ["CA", "FL", "IL", "NY", "PA", "TX", "VA", "WA"]
    rows = []
    for i in range(1, ROW_COUNTS["BillingAccount"] + 1):
        rows.append([f"Billing{i:05d}", f"Account{i:05d}", f"{100 + i} Market Street", "Suite 100", "Metroville", states[i % len(states)], f"{10000 + i % 89999:05d}", f"GRP{i:06d}", f"{10 + i % 89:02d}-{i % 10_000_000:07d}", f"G{i:06d}", "Y" if i % 4 else "N", "Active" if i % 10 else "Inactive", f"555-{i % 1000:03d}-{i % 10_000:04d}", i])
    write_csv("BillingAccount", headers, rows)


def build_account_bridge(customers):
    """Create the populated Account-layer traversal from Customer to invoices.

    AccountID and BillingAccountID are paired one-to-one. Every Customer is a
    member of exactly one Account; accounts 1--10,000 therefore have two
    members and the remaining accounts have one.
    """
    account_headers = ["AccountName", "AccountName2", "LocationAddress1", "LocationAddress2", "LocationCity", "LocationState", "LocationZip", "CompanyCode", "TaxIDNumber", "NumberOfEmployees", "ActivityStatus", "GroupNumber", "LegacyFlexID", "PlanYearStartDate", "PlanYearEndDate", "StandardIndustryCode", "HSAFlag", "HRAFlag", "AnnualizedPremium", "AccountID"]
    member_headers = ["AccountName", "AccountName2", "LocationAddress1", "LocationAddress2", "LocationCity", "LocationState", "LocationZip", "CompanyCode", "CustLastName", "CustFirstName", "CustMiddleInitial", "CustSuffix", "CustDOB", "StartDate", "EndDate", "FSAContributionAmount", "CustBAcctDepartmentName", "Customer_CustomerID", "Account_AccountID", "AccountMemberID"]
    account_rows, account_records = [], []
    states = ["CA", "FL", "IL", "NY", "PA", "TX", "VA", "WA"]
    for account_id in range(1, ROW_COUNTS["Account"] + 1):
        record = {
            "id": account_id, "name": f"Account{account_id:05d}",
            "name2": f"Group{account_id:05d}",
            "address1": f"{100 + account_id} Market Street", "address2": "Suite 100",
            "city": "Metroville", "state": states[account_id % len(states)],
            "zip": f"{10000 + account_id % 89999:05d}", "company": f"COMP{account_id:05d}",
        }
        account_records.append(record)
        account_rows.append([
            record["name"], record["name2"], record["address1"], record["address2"],
            record["city"], record["state"], record["zip"], record["company"],
            f"{10 + account_id % 89:02d}-{account_id % 10_000_000:07d}",
            1 + (account_id % 2), "Active", f"GRP{account_id:06d}",
            f"FLEX{account_id:06d}", "2021-01-01", "2021-12-31", "INS",
            "Y", "N", money(1_200 + account_id % 1_000), account_id,
        ])
    write_csv("Account", account_headers, account_rows)

    member_rows = []
    for customer_id, (last, first, middle, suffix, dob) in enumerate(customers, start=1):
        account_id = ((customer_id - 1) % ROW_COUNTS["Account"]) + 1
        account = account_records[account_id - 1]
        member_rows.append([
            account["name"], account["name2"], account["address1"], account["address2"],
            account["city"], account["state"], account["zip"], account["company"],
            last, first, middle, suffix, iso(dob), "2021-01-01", "", "", "",
            customer_id, account_id, customer_id,
        ])
    write_csv("AccountMember", member_headers, member_rows)

    write_csv("Relation_3", ["Account_AccountID", "BillingAccount_BillingAccountID"],
              ([account_id, account_id] for account_id in range(1, ROW_COUNTS["Relation_3"] + 1)))


def build_rate_versions():
    headers = ["EffectiveDate", "ExpiryDate", "Status", "CreatedByRunID"]
    rows = []
    for version in range(1, 7):
        effective = date(2020 + version, 1, 1)
        expiry = date(2021 + version, 1, 1) if version < 6 else None
        rows.append([iso(effective), iso(expiry), "superseded" if version < 6 else "active", ""])
    write_csv("RATE_VERSION", headers, rows)


def build_contracts(rng: random.Random):
    headers = ["ContractNumber", "LineOfBusiness", "SeriesName", "PlanName", "ActivityStatus", "CoverageType", "BillingMethod", "ModalPremium", "InForceFlag", "PayUpDate", "Duration", "Language", "CreditCardNo", "CardType", "BankingTransitNumber", "BankingAccountType", "BankingAccountNumber", "ContractID", "Product_ProductID", "IssuedRateVersionID", "EffectiveDate", "ExpiryDate"]
    records, rows = [], []
    for i in range(1, ROW_COUNTS["Contract"] + 1):
        product_id = rng.choices(range(1, 16), weights=[8, 7, 7, 6, 5, 8, 7, 4, 5, 3, 8, 7, 4, 5, 3], k=1)[0]
        lob, series, plan, _, _, duration, annual = PRODUCTS[product_id - 1]
        effective = WINDOW_START if i == 1 else weighted_date(rng)
        expiry = add_years(effective, duration) if duration else None
        # ActivityStatus is VARCHAR(10); "Surrender" is the length-compliant
        # representation of the surrendered-policy state.
        status = rng.choices(["Active", "Lapsed", "Surrender"], weights=[78, 14, 8], k=1)[0]
        modal_factor, billing = rng.choice([(12, "Monthly"), (4, "Quarterly"), (1, "Annual")])
        modal = annual / modal_factor * rng.uniform(0.88, 1.18)
        payup = expiry if expiry else add_years(effective, 35)
        record = {"id": i, "effective": effective, "expiry": expiry, "annual": annual * rng.uniform(0.88, 1.18), "modal": modal, "product": product_id, "status": status}
        records.append(record)
        rows.append([f"POL{i:09d}", lob, series, plan, status, "Individual", billing, money(modal), "Y" if status == "Active" else "N", iso(payup), duration, "English", f"4{i:015d}"[-16:], rng.choice(["Visa", "MasterCard", "Amex", "Discover"]), f"{i % 1_000_000_000:09d}", "Checking", f"{i:010d}", i, product_id, active_rate_version(effective), iso(effective), iso(expiry)])
    assert all(r["effective"] <= (r["expiry"] or AS_OF) for r in records)
    write_csv("Contract", headers, rows)
    return records


def build_parties(customers, contracts):
    headers = ["ContractNumber", "CustLastName", "CustFirstName", "CustMiddleInitial", "CustSuffix", "CustDOB", "Role", "BenefitReference", "StartDate", "EndDate", "Customer_CustomerID", "Contract_ContractID", "ContractBenefit_ContractBenefitID", "ContractPartyID"]
    rows = []
    for party_id in range(1, ROW_COUNTS["ContractParty"] + 1):
        contract = contracts[(party_id - 1) % len(contracts)]
        customer_id = ((party_id * 37) % len(customers)) + 1
        last, first, middle, suffix, dob = customers[customer_id - 1]
        rows.append([f"POL{contract['id']:09d}", last, first, middle, suffix, iso(dob), "Owner" if party_id <= 60_000 else "Insured", "", iso(contract["effective"]), iso(contract["expiry"]), customer_id, contract["id"], "", party_id])
    write_csv("ContractParty", headers, rows)


def build_claims(rng: random.Random, contracts):
    headers = ["ClaimNumber", "ClaimDate", "SettlementDate", "WellnessEligibilityDate", "ClaimID", "Contract_ContractID"]
    rows = []
    for i in range(1, ROW_COUNTS["Claim"] + 1):
        contract = rng.choice(contracts)
        claim_date = late_date(rng, contract["effective"], min(contract["expiry"] or AS_OF, AS_OF))
        settlement = claim_date + timedelta(days=rng.randrange(7, 91)) if rng.random() < .82 else None
        wellness = claim_date if rng.random() < .55 else None
        assert contract["effective"] <= claim_date <= (contract["expiry"] or AS_OF)
        rows.append([f"CLM{i:09d}", iso(claim_date), iso(settlement), iso(wellness), i, contract["id"]])
    write_csv("Claim", headers, rows)


def build_invoices(rng: random.Random, contracts):
    headers = ["InvoiceNumber", "PaidDate", "DueDate", "RunDate", "PremiumSubTotal", "PaymentMethod", "PaymentDate", "RemittanceFreq", "BillingAccount_BillingAccountID", "InvoiceID"]
    def rows():
        for i in range(1, ROW_COUNTS["Invoice"] + 1):
            contract = contracts[0] if i == 1 else contracts[(i * 29) % len(contracts)]
            run_date = contract["effective"] if i == 1 else late_date(rng, contract["effective"], min(contract["expiry"] or AS_OF, AS_OF))
            due = run_date + timedelta(days=30)
            paid = run_date + timedelta(days=rng.randrange(0, 25)) if rng.random() < .87 else None
            assert run_date >= contract["effective"]
            yield [f"INV{i:09d}", iso(paid), iso(due), iso(run_date), money(contract["annual"] / rng.choice([1, 4, 12])), rng.choices(["ACH", "Card", "Check"], weights=[66, 27, 7], k=1)[0], iso(paid), rng.choices(["Monthly", "Quarterly", "Annual"], weights=[62, 25, 13], k=1)[0], (contract["id"] % ROW_COUNTS["BillingAccount"]) + 1, i]
    write_csv("Invoice", headers, rows())


def build_wellness(rng: random.Random, contracts):
    program_headers = ["ProgramName", "PartnerGym", "DiscountMaxPct"]
    write_csv("WELLNESS_PROGRAM", program_headers, [["Healthy Start", "City Athletic", "15.00"], ["Move More", "Metro Fitness", "12.00"], ["Tobacco Free", "Wellness Center", "15.00"], ["Heart Health", "Community Gym", "10.00"], ["Nutrition First", "Health Studio", "8.00"]])
    enrollment_headers = ["ContractID", "WellnessProgramID", "EnrollDate", "Status"]
    selected = [contracts[0], *rng.sample(contracts[1:], ROW_COUNTS["WELLNESS_ENROLLMENT"] - 1)]
    enrollments, enrollment_rows = [], []
    for enrollment_id, contract in enumerate(selected, 1):
        end = min(contract["expiry"] or AS_OF, AS_OF)
        enrolled = contract["effective"] if enrollment_id == 1 else late_date(rng, contract["effective"], end)
        enrollments.append({"id": enrollment_id, "contract": contract, "start": enrolled, "end": end})
        enrollment_rows.append([contract["id"], (enrollment_id % 5) + 1, iso(enrolled), rng.choices(["Active", "Complete", "Lapsed"], weights=[70, 20, 10], k=1)[0]])
    write_csv("WELLNESS_ENROLLMENT", enrollment_headers, enrollment_rows)
    return enrollments


def activity_counts(rng: random.Random, count: int, total: int) -> list[int]:
    values = [rng.randint(1, 15) for _ in range(count)]
    high = rng.sample(range(count), 600)
    for index in high:
        values[index] += rng.randint(700, 2_100)
    delta = total - sum(values)
    cursor = 0
    while delta:
        index = high[cursor % len(high)]
        change = min(abs(delta), 25) * (1 if delta > 0 else -1)
        if values[index] + change >= 100:
            values[index] += change
            delta -= change
        cursor += 1
    assert sum(values) == total
    return values


def build_activities(rng: random.Random, enrollments):
    headers = ["EnrollmentID", "ActivityDate", "ActivityType", "VerifiedFlag"]
    counts = activity_counts(rng, len(enrollments), ROW_COUNTS["WELLNESS_ACTIVITY"])
    def rows():
        for enrollment, count in zip(enrollments, counts):
            for occurrence in range(count):
                activity_date = enrollment["start"] if enrollment["id"] == 1 and occurrence == 0 else late_date(rng, enrollment["start"], enrollment["end"])
                assert enrollment["start"] <= activity_date <= enrollment["end"]
                yield [enrollment["id"], iso(activity_date), rng.choices(["Gym Visit", "Step Challenge", "Health Screen", "Nutrition Log"], weights=[52, 28, 8, 12], k=1)[0], "Y" if rng.random() < .72 else "N"]
    write_csv("WELLNESS_ACTIVITY", headers, rows())
    return counts


def build_improvements(rng: random.Random, enrollments):
    headers = ["EnrollmentID", "MeasureDate", "MeasureType", "MeasureValue", "BaselineValue", "ImprovementPct"]
    improvements = defaultdict(list)
    rows = []
    for enrollment in enrollments:
        for measure_no in range(2):
            measured = late_date(rng, enrollment["start"], enrollment["end"])
            pct = round(rng.uniform(2.0, 20.0), 2)
            baseline = round(rng.uniform(20.0, 45.0), 2)
            value = round(baseline * (1 - pct / 100), 2)
            improvements[enrollment["id"]].append((measured, pct))
            rows.append([enrollment["id"], iso(measured), ["BMI", "Smoking", "Exercise"][measure_no % 3], money(value), money(baseline), money(pct)])
    assert len(rows) == ROW_COUNTS["RISK_IMPROVEMENT"]
    write_csv("RISK_IMPROVEMENT", headers, rows)
    return improvements


def build_renewals(rng: random.Random, contracts, enrollments, improvements):
    headers = ["ContractID", "RenewalDate", "NewRateVersionID", "WellnessDiscountPct", "FinalPremium"]
    enrollment_by_contract = {item["contract"]["id"]: item for item in enrollments}
    candidate_lists = {}
    for contract in contracts:
        dates, anniversary = [], add_years(contract["effective"], 1)
        while anniversary <= AS_OF and (contract["expiry"] is None or anniversary < contract["expiry"]):
            dates.append(anniversary)
            anniversary = add_years(anniversary, 1)
        candidate_lists[contract["id"]] = dates
    assert sum(map(len, candidate_lists.values())) >= ROW_COUNTS["POLICY_RENEWAL"]
    selected_dates = []
    ids = list(candidate_lists)
    rng.shuffle(ids)
    for contract_id in ids:
        remaining = ROW_COUNTS["POLICY_RENEWAL"] - len(selected_dates)
        if not remaining:
            break
        selected_dates.extend((contract_id, d) for d in candidate_lists[contract_id][:remaining])
    assert len(selected_dates) == ROW_COUNTS["POLICY_RENEWAL"]
    contract_map = {item["id"]: item for item in contracts}
    rows, discounts = [], []
    for contract_id, renewal_date in selected_dates:
        enrollment = enrollment_by_contract.get(contract_id)
        qualifying = [] if enrollment is None else [pct for measured, pct in improvements[enrollment["id"]] if measured < renewal_date and measured >= enrollment["start"]]
        discount = min(15.00, round(sum(qualifying) / len(qualifying), 2)) if qualifying else 0.00
        contract = contract_map[contract_id]
        assert renewal_date > contract["effective"] and (contract["expiry"] is None or renewal_date < contract["expiry"])
        rows.append([contract_id, iso(renewal_date), active_rate_version(renewal_date), money(discount), money(contract["annual"] * (1 - discount / 100))])
        discounts.append(discount)
    write_csv("POLICY_RENEWAL", headers, rows)
    return discounts


def read_joint_brfss_profiles() -> tuple[list[dict[str, str]], dict[tuple[str, str], list[dict[str, str]]], dict[str, Counter[str]]]:
    """Read the actual staged joint profile distribution, not independent marginals."""
    if not STAGING_BRFSS.exists():
        raise FileNotFoundError(f"Staged BRFSS record file is required for application generation: {STAGING_BRFSS}")
    required = {"AgeBand", "Gender", "SmokingStatus", "DiabetesStatus", "BMIBand", "BMIValue"}
    profiles: list[dict[str, str]] = []
    source_counts = {column: Counter() for column in ("AgeBand", "Gender", "SmokingStatus", "DiabetesStatus", "BMIBand")}
    with STAGING_BRFSS.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) < required:
            raise ValueError(f"{STAGING_BRFSS.name} lacks required application-profile columns")
        for row in reader:
            profile = {column: row[column] for column in required}
            if any(not value for value in profile.values()):
                continue
            if profile["DiabetesStatus"] not in {"yes", "no"}:
                continue
            if profile["SmokingStatus"] not in {"current", "former", "never"}:
                raise ValueError(f"Unexpected staged smoking value: {profile['SmokingStatus']!r}")
            if profile["Gender"] not in {"F", "M"}:
                raise ValueError(f"Unexpected staged gender value: {profile['Gender']!r}")
            if profile["BMIBand"] not in {"under", "normal", "over", "obese"}:
                raise ValueError(f"Unexpected staged BMI band: {profile['BMIBand']!r}")
            bmi = float(profile["BMIValue"])
            if bmi_band_for(bmi) != profile["BMIBand"]:
                raise ValueError(
                    f"BMI band boundary mismatch for staged BMI {bmi}: "
                    f"{profile['BMIBand']!r} is not the verified derived band"
                )
            profiles.append(profile)
            for column, counter in source_counts.items():
                counter[profile[column]] += 1
    if not profiles:
        raise ValueError("No complete yes/no BRFSS profiles are available for application generation")
    by_age_gender: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for profile in profiles:
        by_age_gender[(profile["AgeBand"], profile["Gender"])].append(profile)
    return profiles, by_age_gender, source_counts


def build_applications(rng: random.Random, customers, contracts):
    """Generate APPLICATION rows after legacy output is complete.

    Applications sample complete staged BRFSS records, preserving their observed
    joint smoking, diabetes, BMI, age-band, and gender combinations. Bound rows
    use the customer already connected to each contract through its owner party.
    The first 60,000 CSV rows intentionally map to ContractID 1..60,000 for the
    deterministic identity-preserving load routine.
    """
    profiles, by_age_gender, source_counts = read_joint_brfss_profiles()
    headers = [
        "Customer_CustomerID", "ProductID", "ApplicationDate", "ApplicantAge",
        "Gender", "SmokingStatus", "DiabetesStatus", "BMIValue", "AgeBand",
        "BMIBand", "FaceAmount", "QuotedRateVersionID", "QuotedPremium", "Status",
    ]
    faces, face_weights = [100_000, 250_000, 500_000, 1_000_000], [18, 50, 24, 8]
    rows: list[list[object]] = []
    app_counts = {column: Counter() for column in ("AgeBand", "Gender", "SmokingStatus", "DiabetesStatus", "BMIBand", "Status", "FaceAmount")}

    def append_row(customer_id: int, product_id: int, application_date: date, profile: dict[str, str], status: str, quoted_version: int, quoted_premium: float | None):
        dob = customers[customer_id - 1][4]
        customer_gender = "F" if customer_id % 2 else "M"
        applicant_age = age_at(dob, application_date)
        if customer_gender != profile["Gender"]:
            raise AssertionError("Application gender does not match linked Customer")
        if age_band_for(applicant_age) != profile["AgeBand"]:
            raise AssertionError("Application age band does not match linked Customer date of birth")
        bmi = float(profile["BMIValue"])
        if bmi_band_for(bmi) != profile["BMIBand"]:
            raise AssertionError("Application BMI band does not match raw BMI")
        face = rng.choices(faces, weights=face_weights, k=1)[0]
        rows.append([
            customer_id, product_id, iso(application_date), applicant_age,
            profile["Gender"], profile["SmokingStatus"], profile["DiabetesStatus"],
            f"{bmi:.2f}", profile["AgeBand"], profile["BMIBand"], money(face),
            quoted_version, "" if quoted_premium is None else money(quoted_premium), status,
        ])
        for column, counter in app_counts.items():
            value = face if column == "FaceAmount" else status if column == "Status" else profile[column]
            counter[str(value)] += 1

    for contract in contracts:
        customer_id = ((contract["id"] * 37) % ROW_COUNTS["Customer"]) + 1
        application_date = contract["effective"]
        customer_gender = "F" if customer_id % 2 else "M"
        customer_age_band = age_band_for(age_at(customers[customer_id - 1][4], application_date))
        candidates = by_age_gender.get((customer_age_band, customer_gender), [])
        if not candidates:
            raise ValueError(f"No staged BRFSS profile matches bound customer age and gender {customer_age_band}/{customer_gender}")
        append_row(customer_id, contract["product"], application_date, rng.choice(candidates), "bound", active_rate_version(application_date), contract["modal"])

    unbound_statuses = [("quoted", 15_000), ("declined", 9_000), ("expired", 6_000)]
    for status, count in unbound_statuses:
        for _ in range(count):
            profile = rng.choice(profiles)
            for _attempt in range(10_000):
                application_date = weighted_date(rng)
                customer_id = rng.randint(1, ROW_COUNTS["Customer"])
                customer_gender = "F" if customer_id % 2 else "M"
                applicant_age = age_at(customers[customer_id - 1][4], application_date)
                if customer_gender == profile["Gender"] and age_band_for(applicant_age) == profile["AgeBand"]:
                    break
            else:
                raise RuntimeError("Could not find a Customer consistent with an unbound staged profile")
            product_id = rng.choices(range(1, 16), weights=[8, 7, 7, 6, 5, 8, 7, 4, 5, 3, 8, 7, 4, 5, 3], k=1)[0]
            append_row(customer_id, product_id, application_date, profile, status, active_rate_version(application_date), None)

    if len(rows) != ROW_COUNTS["APPLICATION"]:
        raise AssertionError(f"APPLICATION rows {len(rows):,} do not match target")
    if any(row[-1] != "bound" for row in rows[:ROW_COUNTS["Contract"]]):
        raise AssertionError("Bound applications are not first in CSV order")
    if any(row[-1] == "bound" for row in rows[ROW_COUNTS["Contract"]:]):
        raise AssertionError("Unbound application received bound status")
    write_csv("APPLICATION", headers, rows)
    return {"source_profile_distribution": {key: dict(sorted(value.items())) for key, value in source_counts.items()}, "application_profile_distribution": {key: dict(sorted(value.items())) for key, value in app_counts.items()}}


def file_summary(activity: list[int], discounts: list[float], contracts, applications):
    files = {}
    for table, count in ROW_COUNTS.items():
        size = (OUT / f"{table}.csv").stat().st_size
        files[table] = {"rows": count, "csv_bytes": size, "estimated_sql_data_bytes": int(size * 1.25)}
    summary = {"seed": SEED, "files": files, "total_csv_bytes": sum(v["csv_bytes"] for v in files.values()), "total_estimated_sql_data_bytes": sum(v["estimated_sql_data_bytes"] for v in files.values()), "activity_count_distribution": {"min": min(activity), "median": median(activity), "p90": sorted(activity)[int(len(activity) * .9) - 1], "max": max(activity)}, "wellness_discount": {"zero_count": discounts.count(0.0), "nonzero_min": min(x for x in discounts if x > 0), "nonzero_median": median(x for x in discounts if x > 0), "nonzero_max": max(discounts)}, "contracts_per_rate_version": dict(sorted(Counter(active_rate_version(c["effective"]) for c in contracts).items())), "applications": applications, "profiles": profile_files()}
    (OUT / "volume_generation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {OUT / 'volume_generation_summary.json'}")


def profile_files() -> dict:
    """Scan files without loading large tables, preserving report evidence."""
    date_columns = {
        "Customer": ["CustDOB", "StartDate", "EndDate"],
        "RATE_VERSION": ["EffectiveDate", "ExpiryDate"],
        "Contract": ["PayUpDate", "EffectiveDate", "ExpiryDate"],
        "ContractParty": ["CustDOB", "StartDate", "EndDate"],
        "Claim": ["ClaimDate", "SettlementDate", "WellnessEligibilityDate"],
        "Invoice": ["PaidDate", "DueDate", "RunDate", "PaymentDate"],
        "WELLNESS_ENROLLMENT": ["EnrollDate"],
        "WELLNESS_ACTIVITY": ["ActivityDate"],
        "RISK_IMPROVEMENT": ["MeasureDate"],
        "POLICY_RENEWAL": ["RenewalDate"],
        "APPLICATION": ["ApplicationDate"],
    }
    skew_columns = {
        "BillingAccount": ["OnlineBillingFlag", "ActivityStatus"],
        "RATE_VERSION": ["Status"],
        "Contract": ["ActivityStatus"],
        "Invoice": ["PaymentMethod", "RemittanceFreq"],
        "WELLNESS_ENROLLMENT": ["Status"],
        "WELLNESS_ACTIVITY": ["ActivityType", "VerifiedFlag"],
        "APPLICATION": ["Gender", "SmokingStatus", "DiabetesStatus", "BMIBand", "Status", "FaceAmount"],
    }
    dates, categories = {}, {}
    for table in ROW_COUNTS:
        needed_dates, needed_categories = date_columns.get(table, []), skew_columns.get(table, [])
        if not (needed_dates or needed_categories):
            continue
        minima, maxima = {}, {}
        counters = {column: Counter() for column in needed_categories}
        with (OUT / f"{table}.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for column in needed_dates:
                    value = row[column]
                    if value:
                        minima[column] = min(value, minima.get(column, value))
                        maxima[column] = max(value, maxima.get(column, value))
                for column, counter in counters.items():
                    counter[row[column]] += 1
        if needed_dates:
            dates[table] = {column: {"min": minima.get(column), "max": maxima.get(column)} for column in needed_dates}
        if counters:
            categories[table] = {column: dict(sorted(counter.items())) for column, counter in counters.items()}
    return {"date_ranges": dates, "skewed_categorical_counts": categories}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    customers = build_customers(rng)
    build_products()
    build_billing_accounts(rng)
    build_rate_versions()
    contracts = build_contracts(rng)
    build_parties(customers, contracts)
    build_claims(rng, contracts)
    build_invoices(rng, contracts)
    enrollments = build_wellness(rng, contracts)
    counts = build_activities(rng, enrollments)
    improvements = build_improvements(rng, enrollments)
    discounts = build_renewals(rng, contracts, enrollments, improvements)
    # This deterministic bridge is generated after every random operation that
    # produces the pre-existing files, preserving their byte-for-byte output.
    build_account_bridge(customers)
    application_rng = random.Random(SEED)
    applications = build_applications(application_rng, customers, contracts)
    file_summary(counts, discounts, contracts, applications)


if __name__ == "__main__":
    main()
