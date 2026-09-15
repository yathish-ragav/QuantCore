# Publication References

This is the initial literature set for the QuantCore manuscript. It is deliberately organized by the methodological risks and research traditions that the system addresses. The list is a starting point, not a claim that the literature review is complete.

## Reproducible computational research

[1] R. D. Peng, “Reproducible Research in Computational Science,” *Science*, vol. 334, no. 6060, pp. 1226–1227, 2011. DOI: `10.1126/science.1213847`.

**Use in QuantCore:** motivates the distinction between executable research artifacts, reproducibility, and scientific claims.

## Data snooping and multiple testing

[2] A. W. Lo and A. C. MacKinlay, “Data-Snooping Biases in Tests of Financial Asset Pricing Models,” *The Review of Financial Studies*, vol. 3, no. 3, pp. 431–467, 1990. DOI: `10.1093/rfs/3.3.431`.

[3] D. H. Bailey, J. Borwein, M. López de Prado, and Q. J. Zhu, “The Probability of Backtest Overfitting,” *Journal of Computational Finance*, vol. 20, no. 4, pp. 39–69, 2017. DOI: `10.21314/JCF.2016.322`.

[4] H. White, “A Reality Check for Data Snooping,” *Econometrica*, vol. 68, no. 5, pp. 1097–1126, 2000. DOI: `10.1111/1468-0262.00152`.

[5] C. R. Harvey, Y. Liu, and H. Zhu, “… and the Cross-Section of Expected Returns,” *The Review of Financial Studies*, vol. 29, no. 1, pp. 5–68, 2016. DOI: `10.1093/rfs/hhv059`.

[6] D. H. Bailey and M. López de Prado, “The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality,” *The Journal of Portfolio Management*, vol. 40, no. 5, pp. 94–107, 2014. DOI: `10.3905/jpm.2014.40.5.094`.

**Use in QuantCore:** motivates explicit experiment accounting, out-of-sample evaluation, robustness analysis, and caution around selecting a strategy after repeated trials or searching across many candidate factors.

## Factor research and empirical asset pricing

[7] E. F. Fama and K. R. French, “Common Risk Factors in the Returns on Stocks and Bonds,” *Journal of Financial Economics*, vol. 33, no. 1, pp. 3–56, 1993. DOI: `10.1016/0304-405X(93)90023-5`.

[8] E. F. Fama and K. R. French, “A Five-Factor Asset Pricing Model,” *Journal of Financial Economics*, vol. 116, no. 1, pp. 1–22, 2015. DOI: `10.1016/j.jfineco.2014.10.010`.

**Use in QuantCore:** provides established context for factor definitions, cross-sectional portfolios, and empirical asset-pricing evaluation. QuantCore does not claim that its current factor implementation reproduces these published models unless a specific definition is configured and validated.

## Publication effects and out-of-sample validity

[9] R. D. McLean and J. Pontiff, “Does Academic Research Destroy Stock Return Predictability?,” *The Journal of Finance*, vol. 71, no. 1, pp. 5–32, 2016. DOI: `10.1111/jofi.12365`.

**Use in QuantCore:** supports treating out-of-sample and post-publication behavior as distinct from in-sample backtest performance.

## Trading and implementation costs

[10] A. Frazzini, R. Israel, and T. J. Moskowitz, “Trading Costs of Asset Pricing Anomalies,” Fama-Miller Working Paper, 2012/2014 working-paper versions.

[11] A. J. Patton and B. M. Weller, “What You See Is Not What You Get: The Costs of Trading Market Anomalies,” *Journal of Financial Economics*, vol. 137, no. 2, pp. 515–549, 2020. DOI: `10.1016/j.jfineco.2020.02.012`.

**Use in QuantCore:** motivates explicit transaction-cost assumptions and the separation between gross historical returns and implementable net performance.

## Point-in-time research

The manuscript should include a dedicated literature search for point-in-time accounting/market-data construction, filing-time versus period-end information, revision-aware datasets, survivorship bias, and timestamp/latency effects before submission.

A recent 2026 working-paper literature is relevant to this topic, but it should be treated as contemporary context rather than as a settled foundation. The manuscript should cite peer-reviewed and authoritative sources wherever available and should distinguish working papers from published articles.

## Citation policy

- Prefer the published journal version and DOI when one exists.
- Use working-paper identifiers only when the working paper itself is the relevant source.
- Do not cite a paper merely because it uses the same vocabulary as QuantCore; cite it for a specific methodological or empirical proposition.
- Every citation added to the manuscript should correspond to a claim that can be verified from the cited source.
- The literature review must not be used to imply that QuantCore has already demonstrated an empirical result reported by another paper.
