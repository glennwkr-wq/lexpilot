TITLE: Карта семейств документов LexPilot v1
CATEGORY: taxonomy
STATUS: active

# Карта семейств документов LexPilot v1

Эта карта описывает иерархию шаблонов: специализированный шаблон → общий шаблон подгруппы → общий шаблон семейства.

## claims

- `claim_generic`
- `claim_contract_breach` → parent: `claim_generic`
- `claim_debt_generic` → parent: `claim_contract_breach`
- `claim_supply_debt` → parent: `claim_debt_generic`
- `claim_services_debt` → parent: `claim_debt_generic`
- `claim_rent_debt` → parent: `claim_debt_generic`
- `claim_consumer_generic` → parent: `claim_generic`
- `claim_consumer_refund` → parent: `claim_consumer_generic`
- `claim_consumer_repair` → parent: `claim_consumer_generic`
- `claim_consumer_replacement` → parent: `claim_consumer_generic`
- `claim_penalty`
- `claim_damages`
- `claim_unjust_enrichment`
- `claim_contract_termination`
- `claim_ip_generic` → parent: `claim_generic`
- `claim_copyright_violation` → parent: `claim_ip_generic`
- `claim_trademark_violation` → parent: `claim_ip_generic`

## lawsuits

- `lawsuit_generic`
- `lawsuit_debt_generic` → parent: `lawsuit_generic`
- `lawsuit_supply_debt` → parent: `lawsuit_debt_generic`
- `lawsuit_services_debt` → parent: `lawsuit_debt_generic`
- `lawsuit_rent_debt` → parent: `lawsuit_debt_generic`
- `lawsuit_penalty`
- `lawsuit_damages`
- `lawsuit_unjust_enrichment`
- `lawsuit_contract_termination`
- `lawsuit_consumer`
- `lawsuit_recognition_right`
- `lawsuit_property_recovery`
- `lawsuit_divorce`
- `lawsuit_alimony`
- `lawsuit_parental_rights`

## responses

- `response_generic`
- `response_to_claim`
- `response_consumer`
- `objection_to_claim`
- `objection_to_court_order`
- `objection_to_appeal`

## motions

- `motion_generic`
- `motion_adjournment`
- `motion_evidence_request`
- `motion_restore_deadline`
- `motion_expert_examination`
- `motion_attach_documents`
- `motion_video_conference`
- `motion_interim_measures`

## appeals

- `appeal_generic`
- `appeal_civil`
- `appeal_arbitration`
- `appeal_consumer`
- `appeal_family`

## cassations

- `cassation_generic`
- `cassation_civil`
- `cassation_arbitration`

## contracts

- `contract_generic`
- `supply_contract`
- `services_contract`
- `contractor_agreement`
- `lease_contract`
- `loan_contract`
- `agency_contract`
- `nda`
- `employment_contract`
- `addendum`
- `termination_agreement`

## corporate

- `corporate_generic`
- `corporate_meeting_minutes`
- `director_appointment`
- `share_transfer`
- `corporate_claim`

## labor

- `labor_generic`
- `labor_dismissal`
- `labor_salary_debt`
- `labor_reinstatement`
- `labor_claim`

## enforcement

- `enforcement_generic`
- `bailiff_complaint`
- `enforcement_application`
- `enforcement_motion`
