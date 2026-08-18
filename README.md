# Trend-following QQQ + levier — backtest avec frais IBKR réels

Projet reconstruit from scratch. Objectif : battre le buy&hold **en performance
ajustée au risque** (pas juste en rendement brut), avec un levier modéré et
tous les frais IBKR réels intégrés dès le départ.

## ⚠️ Important — à lire avant de faire confiance aux résultats

- **Ceci n'a pas été testé sur données réelles.** Le code a été validé sur
  des données synthétiques (logique, calcul des coûts, absence de bugs) car
  l'environnement où il a été écrit n'a pas accès à internet. **La première
  chose à faire est de lancer `python main.py` chez toi** pour voir le
  vrai résultat sur QQQ.
- Ce n'est pas un conseil financier. Le levier amplifie les pertes autant que
  les gains, et un backtest n'est jamais une garantie de performance future.
- Un backtest sur ~25 ans d'historique QQQ ne contient que 2-3 vrais crashs
  (2000-2002, 2008, 2020, 2022). Un résultat qui a l'air excellent peut être
  surajusté à ces quelques épisodes — reste prudent avant de risquer de
  l'argent réel.

## Stratégie

- **Instrument** : QQQ (ETF Nasdaq-100)
- **Signal** : Close > SMA(200) → long, sinon → flat (pas de short)
- **Levier** : 1.25x quand long (configurable dans `config.py`)
- **Rebalancement** : uniquement au changement de signal (`signal_only`),
  pour minimiser les frais. Le levier réel dérive donc autour de la cible
  entre deux changements de signal — c'est voulu, un rebalancement fréquent
  coûterait plus cher que ce qu'il rapporte.

## Coûts modélisés (vérifiés le 18/08/2026)

- **Commissions** : IBKR Pro Tiered, $0.0035/action, min $0.35, max 1% de
  la valeur — [source](https://www.interactivebrokers.com/en/pricing/commissions-home.php)
- **Frais réglementaires** : SEC fee + FINRA TAF sur les ventes (faibles mais inclus)
- **Intérêts de marge** : barème réel IBKR Pro USD par palier (blended rate) :
  - $0–100k : 5.13%
  - $100k–1M : 4.63%
  - $1M–50M : 4.38%
  - au-delà : 4.13%
  - [source](https://www.interactivebrokers.com/en/trading/margin-rates.php)
  - **Ces taux bougent avec la Fed Funds Rate.** Ils sont corrects au
    07/08/2026 mais peuvent changer sans préavis — à vérifier périodiquement
    et mettre à jour dans `config.py` (`IBCosts.margin_rate_tiers`).
- **Dividendes** : reçus sur les actions détenues, réinvestis pour le
  buy&hold (comparaison équitable)

## Pourquoi cette approche théoriquement

Un trend-following avec levier modéré cherche à combiner deux effets :
amplifier les gains en tendance haussière (levier) tout en réduisant
l'exposition avant les grosses baisses (signal SMA). L'edge attendu réaliste
est de l'ordre de quelques points de % par an vs buy&hold, principalement via
un **max drawdown bien plus faible**, pas un rendement brut démultiplié.

## Utilisation

```bash
pip install -r requirements.txt
python main.py
```

Génère :
- Un rapport texte (CAGR, vol, max drawdown, Sharpe, Calmar, coûts détaillés)
- `backtest_result.png` : courbe d'équité (échelle log) + drawdown
- `trades.csv` : journal de tous les trades exécutés

## Fichiers

| Fichier | Rôle |
|---|---|
| `config.py` | Tous les paramètres (levier, SMA, coûts IB) — à ajuster ici |
| `data_loader.py` | Téléchargement + cache des données QQQ (yfinance) |
| `strategy.py` | Génération du signal SMA |
| `costs.py` | Calcul des commissions et intérêts de marge réels |
| `backtest.py` | Moteur de simulation du portefeuille |
| `metrics.py` | CAGR, vol, Sharpe, Calmar, max drawdown |
| `main.py` | Point d'entrée : lance tout et génère le rapport |

## Prochaines étapes suggérées

1. Lancer le backtest sur les vraies données et regarder le résultat brut
2. Split train/test (ex: 70/30) pour éviter le surajustement, comme dans le
   projet précédent
3. Tester la robustesse : faire varier `sma_window` et `target_leverage`
   dans une plage raisonnable et vérifier que le résultat ne s'effondre pas
   au moindre changement (signe de surajustement si c'est le cas)
4. Si les résultats sont solides : tester une variante (double SMA, filtre
   de pente, dual momentum) pour comparer
