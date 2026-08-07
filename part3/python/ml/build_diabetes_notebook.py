# Jingrui Feng (jf4446) - database systems project part 3 - diabetes model notebook builder
"""Build the executed diabetes risk-stratification notebook from source-controlled cells."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "notebooks" / "diabetes_risk_model.ipynb"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def main() -> None:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    notebook["cells"] = [
        markdown(
            """
# Diabetes risk-stratification models

I use fixed seed 20260729 for every random operation in this notebook. I train diabetes risk-stratification models from the prepared BRFSS frame. BRFSS is cross-sectional and self-reported, so these models describe concurrent diabetes status rather than future incidence. I do not treat any model in this notebook as a mortality model.
"""
        ),
        markdown(
            """
## 1. Data and preparation

I load the prepared Parquet frame rather than re-deriving BRFSS recodes. The frame preserves 13 one-hot age bands, sex, smoking status, exercise, BMI, the primary label, and `label_sensitivity`. The primary label excludes pre-diabetes. The preparation dropped 4,631 null BMI records and retained the calculated `_TOTINDA` exercise variable because it was verified as redundant with `EXERANY2` among valid responses.

For logistic regression, I drop age band 40-44 as the arbitrary reference category so the 13 age one-hot columns do not become rank-deficient with the intercept. I also use female, never smoking, and exercise yes as explicit reference levels. The tree and K-means inputs retain all 13 age bands.
"""
        ),
        code(
            """
from pathlib import Path
import json
import sys

import pandas as pd
from IPython.display import Image, display

ROOT = Path.cwd().resolve()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "python" / "ml"))

from train_diabetes_risk_model import (
    COEFFICIENTS_PATH,
    FIGURE_DIR,
    METRICS_PATH,
    OUTPUT_DIR,
    PROFILE_PATH,
    SEED,
    run_pipeline,
)

results = run_pipeline()
frame = results["frame"]
metrics = results["metrics"]

print(f"Fixed seed: {SEED}")
print("Shape:", frame.shape)
display(frame.dtypes.rename("dtype").to_frame())
display(frame[["label", "label_sensitivity"]].apply(lambda s: s.value_counts(dropna=False, normalize=True)))
display(results["split"])
"""
        ),
        markdown(
            """
The stratified split preserves the primary positive rate in both partitions. I do not report accuracy because a no-diabetes prediction for every record would score about 85 percent at the observed 14.9 percent prevalence while being useless for a pricing decision.
"""
        ),
        markdown(
            """
## 2. Logistic regression

Business decision: I use this model to support rate revision and risk assessment for a given product. Logistic regression is the primary candidate because its coefficients become directly interpretable rating factors. That is important for underwriting explanations and is a substantive reason to prefer it over a less transparent model.

I evaluate the model on the held-out test set, then refit the same specification on all primary-labelled records for the pipeline export. Calibration matters more than discrimination here because predicted probabilities feed rate calculations directly. A probability must be correct in absolute terms, not merely rank applicants well.
"""
        ),
        code(
            """
display(results["final_coefficients"])
display(pd.DataFrame([results["logistic_metrics"]]))
display(Image(filename=str(FIGURE_DIR / "logistic_precision_recall.png")))
display(Image(filename=str(FIGURE_DIR / "logistic_calibration.png")))
"""
        ),
        markdown(
            """
I use the model as a probability estimator, not as a yes-or-no classifier. Its continuous probability is a rating input, so the 0.5 classification threshold does not describe how the company uses it. AUC and Brier score are the operative measures. The Brier score of 0.112 improves on the 0.127 score from a constant base-rate predictor. I retain the threshold metrics because they document the fitted model, but they are not the decision criterion.
"""
        ),
        markdown(
            """
## 3. Decision tree

Business decision: I use the tree as an interpretability comparison for rate revision and risk assessment. I tune depth with five-fold stratified cross-validation on the same training split. A tree can show threshold interactions, but those thresholds are harder to defend to a regulator than a coefficient for a named risk factor.
"""
        ),
        code(
            """
tree_cv = pd.DataFrame(
    {
        "max_depth": [int(k) for k in results["tree_metrics"]["cv_results"]],
        "cross_validation_auc": list(results["tree_metrics"]["cv_results"].values()),
    }
)
display(tree_cv)
display(pd.DataFrame([results["tree_metrics"]]).drop(columns=["cv_results"]))
display(Image(filename=str(FIGURE_DIR / "decision_tree_top_levels.png")))
display(Image(filename=str(FIGURE_DIR / "tree_precision_recall.png")))
display(Image(filename=str(FIGURE_DIR / "tree_calibration.png")))
"""
        ),
        markdown(
            """
I compare the held-out metrics honestly in the result table. If the tree were stronger on AUC, I would still need to explain its threshold tradeoff. In this run the tree is weaker than logistic regression, so the interpretability argument and the measured performance point in the same direction.
"""
        ),
        markdown(
            """
## 4. K-means segmentation

Business decision: I use segmentation to identify potential product tiers and wellness-outreach groups. K-means receives no diabetes label. I standardize the complete encoded feature set first because BMI and the one-hot inputs otherwise have incompatible scales. Observed diabetes prevalence appears only after fitting as a validation description.
"""
        ),
        code(
            """
k_selection = pd.DataFrame(
    {
        "k": [int(k) for k in results["kmeans_metrics"]["inertia"]],
        "inertia": list(results["kmeans_metrics"]["inertia"].values()),
        "silhouette_score": list(results["kmeans_metrics"]["silhouette"].values()),
    }
)
display(k_selection)
display(Image(filename=str(FIGURE_DIR / "kmeans_selection.png")))
display(results["clusters"])
"""
        ),
        markdown(
            """
I select the reported k using the elbow and silhouette diagnostics together. The cluster names describe their modal values and do not constitute pricing classes. A higher-BMI, lower-exercise cluster can guide wellness outreach, while simpler lower-risk clusters can guide product presentation.

K-means uses Euclidean distance, which treats all pairs of one-hot categories as equidistant. That is a poor fit for this mostly categorical data and is the main reason the silhouette score is only 0.221. K-modes or Gower distance would suit mixed data better. I retain K-means because the assignment requires it and the resulting clusters are interpretable, while stating the limitation directly.
"""
        ),
        markdown(
            """
## 5. Sparsity argument

Business decision: I need a model because a lookup table cannot give a stable rate to every profile. The staging analysis found 605 observed profiles of 624 possible. Nineteen have zero records, 34 have exactly one record, and 272 have fewer than 30 records. A single additional diabetic response changes a one-record empirical rate by 50 percentage points.
"""
        ),
        code(
            """
display(results["sparse"])
print("Zero-record lookup result: no STG_BRFSS profile row exists for this combination.")
display(results["zero"])
"""
        ),
        markdown(
            """
The zero-record example has no empirical prevalence to look up, yet the fitted logistic model returns a probability. This is the practical reason the company cannot price from a `STG_BRFSS` lookup table alone.

The same staging query found two one-record profiles with a diabetic response. A lookup table would assign each an empirical prevalence of 100 percent from one observation, while the fitted probabilities are much lower.

| AgeBand | Gender | SmokingStatus | BMIBand | ExerciseFreq | Records | EmpiricalPrevalence | PredictedProbability |
|---|---|---|---|---|---|---|---|
| 40-44 | M | former | under | no | 1 | 1.0000 | 0.0449 |
| 55-59 | F | never | under | no | 1 | 1.0000 | 0.0898 |
"""
        ),
        markdown(
            """
## 6. Sensitivity analysis on pre-diabetes

Business decision: I test whether the binary decision to map pre-diabetes to no in `RISK_FACTOR` changes the core rate-revision result. The sensitivity model folds the 1,085 pre-diabetes records into the positive label and uses the same logistic specification. This is a measurement of the documented source-traceability decision, not a three-level rating factor.
"""
        ),
        code(
            """
display(results["sensitivity"])
display(pd.DataFrame([results["sensitivity_metrics"]]))
print(
    "Primary AUC:", f"{results['logistic_metrics']['auc']:.3f}",
    "Sensitivity AUC:", f"{results['sensitivity_metrics']['auc']:.3f}",
)
"""
        ),
        markdown(
            """
## 7. Validation against external sources

Business decision: I check whether the model's age pattern agrees directionally with independent external data before using it in a pricing pipeline. The first check compares predicted diabetes prevalence against the WONDER diabetes-to-all-cause ratio for the 2022-2024 cohort, identified in staging by `SourceYear = 2023`. Prevalence and mortality attribution are different measures, so I assess direction rather than numerical equality. The second check compares age ordering with lives-weighted SSA mortality rates.
"""
        ),
        code(
            """
display(results["wonder_comparison"])
display(Image(filename=str(FIGURE_DIR / "wonder_directional_comparison.png")))
display(results["ssa_ordering"])
display(Image(filename=str(FIGURE_DIR / "ssa_ordering_comparison.png")))
print(json.dumps(results["validation_metrics"], indent=2))
"""
        ),
        markdown(
            """
The WONDER comparison gives positive rank correlations for both sexes. Spearman correlations are F=0.595 and M=0.548. They are directionally consistent, but eight age groups cannot support a significance claim because the approximate 0.05 critical value is 0.74. I report them as directional evidence only.

The model probability declines from 75-79 to the open-ended 80-99 band for both sexes while SSA mortality continues to rise. This is expected epidemiology rather than a model defect. Survivorship means people with diabetes can die earlier, leaving a healthier surviving population above age 80. Diabetes can also be underdiagnosed in the very old, and the open-ended 80-99 band mixes twenty years of substantially different ages. Prevalence and mortality are different quantities, so they need not move together at the oldest ages.

This result validates the source separation in the design. SSA supplies absolute mortality, while the model supplies relative differentiation rather than the mortality baseline. The same pattern helps explain the subgroup AUC of 0.652 for age 80-99 compared with 0.803 for age 35-39. The oldest band is the hardest group to discriminate for the same survivorship and aggregation reasons, as shown in the fairness results below.
"""
        ),
        markdown(
            """
## 8. Fairness and limitations

United States permissibility is jurisdiction-specific. Age, smoking status, diabetes status, and BMI are candidate rating inputs only where the company can show a sound actuarial basis and a valid rationale, then comply with applicable state law and filing rules. Gender requires separate review because its use is restricted in some United States jurisdictions and prohibited for insurance pricing in the European Union. The National Association of Insurance Commissioners states that external-data underwriting models need sound actuarial principles, transparent inputs, and unfair-discrimination review. The European Commission's Test-Achats guidance requires unisex premiums and benefits for new European Union contracts.

The frame retains 42,766 of 50,000 records, so 7,234 records do not remain after preparation. BMI accounts for 4,631 drops, and the documented nonresponse patterns mean the exclusions are a coherent less-willing respondent group rather than scattered noise. Training is unweighted, so probabilities reflect the BRFSS sample rather than the United States population. Calibration and subgroup monitoring are the controls that address that limitation.
"""
        ),
        code(
            """
display(results["sex_auc"])
display(results["age_auc"])
"""
        ),
        markdown(
            """
## 9. Output for the pipeline

I export the candidate logistic coefficients, one predicted probability for every possible `STG_BRFSS` profile, and the evaluation metrics. The profile export has all 624 combinations using the verified staging vocabulary `AgeBand`, `Gender`, `SmokingStatus`, `BMIBand`, and `ExerciseFreq`. It is the direct input shape for future `RISK_FACTOR` construction. This notebook does not populate `RISK_FACTOR`, `RATE_VERSION`, or `RATE`.
"""
        ),
        code(
            """
profiles = pd.read_csv(PROFILE_PATH)
print("Coefficient export:", COEFFICIENTS_PATH)
print("Profile export:", PROFILE_PATH)
print("Metrics export:", METRICS_PATH)
print("Profile shape:", profiles.shape)
print("Vocabulary:", json.dumps(metrics["profile_vocabulary"], indent=2))
display(profiles.head())
"""
        ),
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
