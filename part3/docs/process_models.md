# Jingrui Feng (jf4446) - database systems project part 3 - quote to policy process models

# Quote-to-policy process models

I use UML-style activity diagrams with swimlanes for the documented application workflows. These are activity diagrams rendered with Mermaid, not strict BPMN diagrams. Each diagram makes the normal path, significant extension branches, and database boundary visible.

## UC-1 Applicant obtains a quote

```mermaid
flowchart LR
    start((Start))
    endQuote((Quote returned))
    endCorrection((End))
    endUnavailable((End))
    endNoConvert((End))
    subgraph Applicant
        submit[Submit profile, face amount, and product]
        correct[Correct profile]
        receive[Receive quote and RateVersionID]
        convert{Convert quote?}
    end
    subgraph Web_Application[Web Application]
        validate[Validate profile]
        complete{Profile complete?}
        returnQuote[Calculate and return premium]
        unavailable[Explain unavailable profile]
    end
    subgraph Database
        active[Read active RATE_VERSION]
        match[Find matching RISK_FACTOR and RATE]
        found{Matching rate row?}
        application[Write APPLICATION as quoted]
    end
    start --> submit --> validate --> complete
    complete -- No --> correct --> endCorrection
    complete -- Yes --> active --> match --> found
    found -- No --> unavailable --> endUnavailable
    found -- Yes --> application --> returnQuote --> receive --> convert
    convert -- Yes --> endQuote
    convert -- No --> endNoConvert
```

![UC-1 process](../diagrams/uc1_process.png)

I show the application profile, face amount, and active `RATE_VERSION` lookup because the quote must use a current rate book. A successful quote writes `APPLICATION` with status `quoted`. An incomplete or unmatched profile does not create a policy, and an unconverted quote remains an application without a `Contract`.

## UC-2 Applicant converts a quote to a policy

```mermaid
flowchart LR
    start((Start))
    endBound((Policy bound))
    endRequote((End))
    endValidation((End))
    endBilling((End))
    subgraph Applicant
        accept[Accept quote and provide effective date]
        acceptRevised{Accept revised premium?}
        correct[Correct identity or party data]
    end
    subgraph Web_Application[Web Application]
        determine[Determine rate version for effective date]
        changed{Rate version changed since quote?}
        requote[Recalculate quote]
        validate[Validate identity and party data]
        valid{Valid?}
        confirm[Confirm binding]
    end
    subgraph Database
        active[Read active RATE_VERSION and matching RATE]
        application[Read APPLICATION profile and quote]
        customer[Identify or create Customer]
        contract[Create Contract with IssuedRateVersionID and ApplicationID]
        bound[Update APPLICATION status to bound]
        party[Create ContractParty]
        billing[Establish AccountMember to Account to Relation_3 to BillingAccount path]
        billingReady{Billing path established?}
    end
    start --> accept --> determine --> active --> changed
    changed -- Yes --> requote --> acceptRevised
    acceptRevised -- No --> endRequote
    acceptRevised -- Yes --> validate
    changed -- No --> validate
    validate --> valid
    valid -- No --> correct --> endValidation
    valid -- Yes --> application --> customer --> contract --> bound --> party --> billing --> billingReady
    billingReady -- No --> endBilling
    billingReady -- Yes --> confirm --> endBound
```

![UC-2 process](../diagrams/uc2_process.png)

I use the changed-rate branch to make the policy-freezing rule concrete. Binding reads the persisted `APPLICATION`, writes its identifier to `Contract.ApplicationID`, and writes the version active on the effective date to `Contract.IssuedRateVersionID`. The billing branch uses the declared account path and does not create or imply a direct contract-to-invoice relationship.

## UC-3 Policyholder reports wellness participation

```mermaid
flowchart LR
    start((Start))
    endRecorded((Screening recorded))
    endRejected((End))
    endUnverified((End))
    subgraph Policyholder
        select[Select wellness program and enrollment date]
        screening[Record biometric baseline and current measurement]
    end
    subgraph Participating_Gym[Participating Gym]
        report[Report activity and enrollment identifier]
    end
    subgraph Web_Application[Web Application]
        beforeRenewal{Enrollment before next renewal?}
        screenBeforeRenewal{Screening before next renewal?}
        verify[Check enrollment and activity verification]
        enrolled{Active enrollment?}
        verified{Activity verified?}
        reject[Reject report]
        flag[Store unverified activity]
        unchanged[Show activity alone leaves credit unchanged]
        calculate[Calculate measured improvement]
    end
    subgraph Database
        program[Read WELLNESS_PROGRAM and Contract]
        enrollment[Write WELLNESS_ENROLLMENT]
        activity[Write WELLNESS_ACTIVITY]
        improvement[Write dated RISK_IMPROVEMENT]
    end
    start --> select --> program --> beforeRenewal
    beforeRenewal -- No --> reject --> endRejected
    beforeRenewal -- Yes --> enrollment --> report --> verify --> enrolled
    enrolled -- No --> reject --> endRejected
    enrolled -- Yes --> verified
    verified -- No --> flag --> endUnverified
    verified -- Yes --> activity --> unchanged --> screening --> screenBeforeRenewal
    screenBeforeRenewal -- No --> reject --> endRejected
    screenBeforeRenewal -- Yes --> calculate --> improvement --> endRecorded
```

![UC-3 process](../diagrams/uc3_process.png)

I show enrollment, verified activity, and biometric screening as separate steps. Activity records participation but leaves the credit unchanged. A dated measurement before the next renewal writes `RISK_IMPROVEMENT`, which supplies the evidence for a future renewal credit.

## UC-4 System performs scheduled rate revision

```mermaid
flowchart LR
    start((Start))
    endSuccess((Refresh completed))
    endSourceFailure((End))
    endModelFailure((End))
    endPublishFailure((End))
    subgraph Controlled_Operations[Controlled Operations]
        parameters[Select authorized mortality cohort and loading factor]
    end
    subgraph Scheduler
        trigger[Trigger scheduled refresh]
    end
    subgraph Refresh_Job[Scheduled Refresh Job]
        run[Create running DATA_REFRESH_RUN]
        sources{Required sources available?}
        failSource[Record failed run]
        publish[Create RATE_VERSION and RATE rows]
        published{Publication complete?}
        failPublish[Record failed run]
        complete[Record NewRateVersionID and success]
    end
    subgraph Database
        staging[Read STG_BRFSS_RECORD, STG_BRFSS, STG_NHANES, and STG_MORTALITY]
        risks[Write RISK_FACTOR rows]
    end
    subgraph Model_Scoring[Model Scoring]
        score[Apply approved diabetes-risk coefficients]
        plausible{Output plausible?}
        failModel[Return validation failure]
    end
    start --> parameters --> trigger --> run --> sources
    sources -- No --> failSource --> endSourceFailure
    sources -- Yes --> staging --> score --> plausible
    plausible -- No --> failModel --> failSource
    plausible -- Yes --> risks --> publish --> published
    published -- No --> failPublish --> endPublishFailure
    published -- Yes --> complete --> endSuccess
```

![UC-4 process](../diagrams/uc4_process.png)

I show UC-4 as a scheduler-driven process to distinguish it from the synchronous quote path. Controlled operations can choose an authorized mortality cohort and loading factor before the job starts. The process demonstrates the asynchronous pricing mechanism through `DATA_REFRESH_RUN`, staging input, approved diabetes-risk scoring, risk-factor construction, and a separately published rate version. Failed sources, implausible model output, and failed publication never replace the existing active rate book.

## UC-5 Policy renewal is repriced with a wellness offset

```mermaid
flowchart LR
    start((Start))
    endRenewal((Renewal recorded))
    endReview((End))
    subgraph Scheduler
        identify[Identify eligible contract anniversary]
    end
    subgraph Renewal_Service[Renewal Service]
        rate[Find active rate version and matching rate]
        available{Rate available?}
        review[Route renewal for review]
        wellness[Read qualifying improvement before renewal date]
        eligible{Qualifying improvement?}
        zero[Set discount to zero]
        cap{Discount above 15 percent?}
        capped[Set discount to 15 percent]
        calculate[Calculate final premium]
    end
    subgraph Database
        contract[Read Contract]
        application[Read APPLICATION profile and face amount]
        rateTables[Read RATE_VERSION, RATE, and RISK_FACTOR]
        improvements[Read WELLNESS_ENROLLMENT and RISK_IMPROVEMENT]
        renewal[Write POLICY_RENEWAL with NewRateVersionID]
    end
    start --> identify --> contract --> application --> rateTables --> rate --> available
    available -- No --> review --> endReview
    available -- Yes --> improvements --> wellness --> eligible
    eligible -- No --> zero --> calculate
    eligible -- Yes --> cap
    cap -- Yes --> capped --> calculate
    cap -- No --> calculate
    calculate --> renewal --> endRenewal
```

![UC-5 process](../diagrams/uc5_process.png)

I added this diagram because it is the point where new pricing and wellness participation meet. Renewal reads the profile and face amount through `Contract.ApplicationID`, then uses `POLICY_RENEWAL.NewRateVersionID` for the version active on the renewal date. The existing contract keeps its original `IssuedRateVersionID`. Only improvement dated before renewal is considered, and the discount branch makes the 15 percent cap visible.

## Synchronous and asynchronous boundary

```mermaid
flowchart TB
    startSync((Applicant request))
    endSync((Quote or bound policy))
    startAsync((Timer event))
    endAsync((Published rate version))
    subgraph Synchronous_Transactional_Path[Synchronous transactional path]
        quote[Web application reads active RATE_VERSION and RATE]
        bind[Bind Contract with IssuedRateVersionID]
        pinned[In-force Contract retains its own issue-time version]
        quote --> bind --> pinned
    end
    subgraph Shared_Rate_Data[Shared rate data]
        rates[RATE_VERSION and RATE]
        independent[Independent transactions, no mutual blocking]
    end
    subgraph Asynchronous_Repricing_Path[Asynchronous repricing path]
        lake[Blob Storage and Synapse serverless]
        refresh[Timer-triggered Azure Function refresh]
        stage[Read staging and score approved model]
        publish[Write RISK_FACTOR, new RATE_VERSION, and RATE only]
        noContractWrite[No Contract write. Existing IssuedRateVersionID stays unchanged]
        lake --> refresh --> stage --> publish
        publish --> noContractWrite
    end
    startSync --> quote
    rates --> quote
    bind --> endSync
    startAsync --> refresh
    publish --> rates
    publish --> endAsync
    independent -. Applies to both paths .-> rates
    pinned -. Later publication does not change pin .-> rates
```

![Asynchronous boundary](../diagrams/async_boundary.png)

I designed this boundary diagram to show why the first two required mechanisms are properties of the design. The quote and bind path synchronously reads the active `RATE_VERSION` and `RATE`, while the timer-triggered refresh writes a new version in an independent transaction. The annotation on the asynchronous path states that it writes `RISK_FACTOR`, `RATE_VERSION`, and `RATE` only. There is no write edge from the repricing path to `Contract`, so an in-force `Contract` keeps its own `IssuedRateVersionID` after publication.

## Rendering

I rendered the PNG files from the editable Mermaid sources in `diagrams/src/` with this command pattern:

```bash
node_modules/.bin/mmdc -p diagrams/puppeteer-config.json -c diagrams/mermaid-config.json -i diagrams/src/uc1_process.mmd -o diagrams/uc1_process.png -w 1800 -H 1200 -b white
```

The same command was run once for each source file. `diagrams/mermaid-config.json` sets black borders and lines, white fills, black text, and linear connectors. `diagrams/puppeteer-config.json` sets the Chromium sandbox option needed by the local renderer.
