# Jingrui Feng (jf4446) - database systems project part 3 - model role in pricing

# Model role in pricing

I use the diabetes model to estimate residual diabetes risk among applicants
who disclose no diabetes. The quote form collects diabetes status directly, so
the applicant's disclosure remains authoritative. The model refines the
disclosed non-diabetic class and does not override the answer an applicant
reported. Two applicants can disclose no diabetes while having different
probabilities of undiagnosed or emerging diabetes risk based on age, gender,
smoking status, BMI, and exercise.

This design is not circular. The model estimates diabetes probability from
BRFSS data, while the pricing pipeline uses the applicant's disclosed diabetes
status to select the diagnosed or disclosed non-diabetic path. A disclosed
diabetes answer receives the diagnosed-diabetes effect from the WONDER-derived
relative risk. The model only differentiates residual risk within the disclosed
non-diabetic path.

## Published risk-factor construction

The local database currently contains 3,120 `RISK_FACTOR` rows from five
successful refresh runs. Each run writes 624 rows that cover the supported age,
gender, smoking, BMI, and disclosed-diabetes profiles.

I keep the source roles separate. SSA lives-weighted band rates provide the
absolute population mortality baseline by age band and gender. Published
external actuarial inputs provide the smoking and BMI all-cause mortality
relativities. I declare those values as named refresh parameters because no
dataset in the lake stratifies all-cause mortality by smoking status or BMI.
The WONDER-derived relative risk provides the diagnosed-diabetes effect. The
model supplies residual differentiation within the disclosed non-diabetic
class. The pipeline scales that model probability by the named undiagnosed
fraction parameter.

The model does not provide mortality weights for smoking or BMI. Its
coefficients corroborate the direction and ordering of those diabetes-risk
factors, while the mortality magnitudes come from the documented external
inputs. This avoids representing a diabetes-association coefficient as a direct
all-cause mortality estimate.

This role also connects the model to the wellness mechanism. Smoking status,
BMI, and exercise are the three changeable model inputs. Age and gender are not
changeable. Wellness participation records activity, while a dated measured
improvement can support a renewal credit. The company can therefore base that
credit on measured change in factors related to residual diabetes risk rather
than on an arbitrary discount.

K-means remains descriptive. I use its clusters for product presentation and
wellness outreach, not as pricing classes.
