# Turkiye — ABM Election Forecast

Turkey general-election forecasting with **agent-based modelling**, entirely
independent of opinion polls. Voters are modelled as agents with demographic,
socio-economic and ideological attributes; party positions come from
expert/manifesto data; voting rules are screened against historical YSK
results and then deployed forward.

## Method

Follows Gao et al. (2022, PLoS ONE 17(6):e0270194) and Hummel & Rothschild
(2013, AEA):

1. **Data**: YSK election results (2002-2023, province level), TÜİK MEDAS
   demographics, TCMB EVDS / TÜFE / ENAG / İTO economics, CHES + MARPOR
   ideology positions.
2. **Voting rules**: single-variable regressions -> "voting preference
   intervals" (the election history is too short for multi-variable models).
3. **Screening**: simulate past elections with randomized rule weights; keep
   models that reproduce history within ±2.5% per party.
4. **Forecast**: average the surviving models over 100 simulation runs, using
   extrapolated demographics + latest economics. D'Hondt + 10% threshold for
   seats.

## Layout

```
data/raw/          untouched source exports
data/processed/    clean CSVs (elections, demographics, economics, ideology)
scrapers/          YSK, TÜİK, EVDS, ENAG, İTO collectors
ideology/          party positioning (CHES/MARPOR), voter ideal-point maps
abm/               agents, voting rules, screening, simulation core
experiments/       retro-forecasts (2023 first), notebooks
report/            outputs
```

## Roadmap

- [ ] M1: 2023 retro-forecast — YSK + TÜİK + ideology, no economics
- [ ] M2: economics layer (EVDS/TÜFE/ENAG/İTO) as trend terms, re-screen
- [ ] M3: forward forecast + seat projection + publication page