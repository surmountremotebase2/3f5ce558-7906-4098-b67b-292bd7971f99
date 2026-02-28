#Type code here
import math
from surmount.base_class import Strategy, TargetAllocation
from surmount.data import InstitutionalOwnership, InsiderTrading, SocialSentiment

class TradingStrategy(Strategy):
    def __init__(self):
        # §2-5 UNIVERSES: Precisely defined asset sleeves
        self.tech_tickers = ["NVDA", "AVGO", "PLTR", "TQQQ", "SOXL"]
        self.tech_benchmark = "QQQ"
        
        self.biotech_tickers = ["CRSP", "VRTX", "NVO"]
        self.biotech_benchmark = "XBI"
        
        # Exact digital asset pairs to execute on connected exchanges
        self.crypto_tickers = ["BTCUSD", "ETHUSD", "SOLUSD", "SUIUSD"]
        self.crypto_benchmark = "BTCUSD"
        
        self.metals_tickers = ["SLV", "FNV", "NUGT"]
        self.metals_benchmark = "GLD"
        
        # Macro proxies
        self.macro_tickers = ["VIXY", "UUP", "SPY"] 
        
        self.benchmarks = [self.tech_benchmark, self.biotech_benchmark, self.crypto_benchmark, self.metals_benchmark]
        self.tradeable_assets = self.tech_tickers + self.biotech_tickers + self.crypto_tickers + self.metals_tickers
        self.tickers = self.tradeable_assets + self.benchmarks + self.macro_tickers
        
        self.data_list = []
        for ticker in self.tradeable_assets + self.benchmarks:
            self.data_list.append(SocialSentiment(ticker))
            self.data_list.append(InstitutionalOwnership(ticker))
            self.data_list.append(InsiderTrading(ticker))

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    # =====================================================================
    # INNOVATIVE, CRASH-RESISTANT QUANTITATIVE ENGINE 
    # =====================================================================
    def get_return(self, prices, days):
        valid = [p for p in prices if p > 0]
        if len(valid) < days + 1: return 0
        return (valid[-1] - valid[-(days+1)]) / valid[-(days+1)]

    def get_stdev(self, data_array):
        valid = [p for p in data_array if p is not None]
        length = len(valid)
        if length < 2: return 0.01
        mean = sum(valid) / length
        variance = sum((x - mean) ** 2 for x in valid) / length
        return math.sqrt(variance) if variance > 0 else 0.01

    def get_ema(self, prices, period):
        valid = [p for p in prices if p > 0]
        if len(valid) < period: return valid[-1] if valid else 0.01
        k = 2 / (period + 1)
        ema = sum(valid[:period]) / period
        for price in valid[period:]:
            ema = (price - ema) * k + ema
        return ema

    def get_macd(self, prices):
        """Calculates MACD Histogram to confirm trend acceleration."""
        ema_12 = self.get_ema(prices, 12)
        ema_26 = self.get_ema(prices, 26)
        macd_line = ema_12 - ema_26
        return macd_line

    def calculate_cms(self, ticker, ohlcv, data_stream):
        """§1.2: 5-Factor Composite Momentum Score with Skip-Day Rule"""
        closes = [x.get(ticker, {}).get("close", 0) for x in ohlcv]
        volumes = [x.get(ticker, {}).get("volume", 0) for x in ohlcv]
        
        if len(closes) < 50 or closes[-1] <= 0 or closes[-48] <= 0:
            return -999 
            
        # 1. Absolute Momentum & Skip-Day Rule (25%)
        skip_day_return = (closes[-6] - closes[-48]) / closes[-48]
        if skip_day_return <= 0:
            return -999 
            
        # 2. Risk-Adjusted 12-day Return (30%)
        ret_12d = self.get_return(closes, 12)
        vol_12d = self.get_stdev(closes[-12:])
        risk_adj_ret = ret_12d / vol_12d
        
        # 3. Sentiment Acceleration (20%)
        social_data = data_stream.get(("social_sentiment", ticker), [])
        sent_accel = 0
        if len(social_data) >= 20:
            sent_5 = sum([x.get("twitterSentiment", 0.5) for x in social_data[-5:]]) / 5
            sent_20 = sum([x.get("twitterSentiment", 0.5) for x in social_data[-20:]]) / 20
            sent_accel = sent_5 - sent_20

        # 4. Institutional/Insider Flow (15%)
        inst_signal = 0
        insider_data = data_stream.get(("insider_trading", ticker), [])
        
        # §6.4 Insider Intelligence: Bearish vs Bullish Clustering
        bearish_cluster = False
        if len(insider_data) >= 3:
            recent_sales = sum(1 for trade in insider_data[-5:] if "sell" in trade.get("transactionType", "").lower())
            if recent_sales >= 3:
                bearish_cluster = True
            elif "buy" in insider_data[-1].get("transactionType", "").lower() or "purchase" in insider_data[-1].get("transactionType", "").lower():
                inst_signal += 1
                
        inst_own_data = data_stream.get(("institutional_ownership", ticker), [])
        if len(inst_own_data) > 0 and inst_own_data[-1].get("increasedPositionsChange", 0) > 0:
            inst_signal += 1

        if bearish_cluster: 
            return -999 # Hard exclusion on bearish insider clustering

        # 5. Volume Confirmation Ratio (10%)
        vol_10 = sum(volumes[-10:]) / 10 if sum(volumes[-10:]) > 0 else 1
        vol_50 = sum(volumes[-50:]) / 50 if sum(volumes[-50:]) > 0 else 1
        vol_ratio = vol_10 / vol_50
        
        cms = (0.30 * risk_adj_ret) + (0.25 * skip_day_return) + (0.20 * sent_accel) + (0.15 * inst_signal) + (0.10 * vol_ratio)
        return cms

    def run(self, data):
        ohlcv = data.get("ohlcv", [])
        if len(ohlcv) < 50:
            return TargetAllocation({})
            
        target_weights = {}

        # =====================================================================
        # §6 REGIME DETECTION & DYNAMIC OVERLAYS
        # =====================================================================
        vix_prices = [x.get("VIXY", {}).get("close", 0) for x in ohlcv]
        vix_sma_5 = sum([p for p in vix_prices[-5:] if p > 0]) / 5 if len(vix_prices) >= 5 else 15
        
        uup_closes = [x.get("UUP", {}).get("close", 0) for x in ohlcv]
        uup_sma_50 = sum([p for p in uup_closes[-50:] if p > 0]) / 50 if len(uup_closes) >= 50 else 0
        dollar_weakening = len(uup_closes) > 0 and uup_closes[-1] < uup_sma_50
        
        # §3.4 XBI Regime Adaptation
        xbi_closes = [x.get("XBI", {}).get("close", 0) for x in ohlcv]
        xbi_sma_50 = sum([p for p in xbi_closes[-50:] if p > 0]) / 50 if len(xbi_closes) >= 50 else 0
        biotech_risk_off = len(xbi_closes) > 0 and xbi_closes[-1] < xbi_sma_50
        
        # Base Allocation Budgets
        sleeve_budgets = {
            "tech": 0.30,
            "biotech": 0.15 if biotech_risk_off else 0.17, # Reduce if XBI < 50 SMA
            "crypto": 0.28,
            "metals": 0.12,
        }
        
        # §4.4 Crypto Circuit Breaker Analysis
        btc_closes = [x.get("BTCUSD", {}).get("close", 0) for x in ohlcv]
        btc_valid = [p for p in btc_closes[-30:] if p > 0]
        btc_30d_high = max(btc_valid) if btc_valid else 0.01
        btc_drawdown = (btc_30d_high - btc_closes[-1]) / btc_30d_high if btc_30d_high > 0 else 0
        
        if btc_drawdown > 0.25: # Tier 3 Red Circuit Breaker
            sleeve_budgets["crypto"] = 0.15
            sleeve_budgets["metals"] += 0.13
            
        # §6.3 Cross-Sleeve Momentum Rotation
        bench_scores = {
            "tech": self.calculate_cms(self.tech_benchmark, ohlcv, data),
            "biotech": self.calculate_cms(self.biotech_benchmark, ohlcv, data),
            "crypto": self.calculate_cms(self.crypto_benchmark, ohlcv, data),
            "metals": self.calculate_cms(self.metals_benchmark, ohlcv, data)
        }
        
        valid_bench = {k: v for k, v in bench_scores.items() if v != -999}
        if len(valid_bench) >= 2:
            top_sleeve = max(valid_bench, key=valid_bench.get)
            bottom_sleeve = min(valid_bench, key=valid_bench.get)
            sleeve_budgets[top_sleeve] += 0.03
            sleeve_budgets[bottom_sleeve] -= 0.03

        # §6.1 Master Risk Overlays (VIX)
        vix_regime = 1
        if vix_sma_5 >= 30:   
            vix_regime = 4
            sleeve_budgets = {"tech": 0.20, "crypto": 0.20, "biotech": 0.12, "metals": 0.20}
        elif vix_sma_5 >= 25: 
            vix_regime = 3
            sleeve_budgets["tech"] -= 0.05
            sleeve_budgets["crypto"] -= 0.03
            sleeve_budgets["metals"] += 0.05
            
        if dollar_weakening: sleeve_budgets["metals"] += 0.03
        else: sleeve_budgets["metals"] -= 0.03

        # =====================================================================
        # ASSET EVALUATION & ADVANCED PROTOCOLS
        # =====================================================================
        cms_scores = {}
        volatilities_21d = {}
        
        btc_14d = self.get_return(btc_closes, 14)
        eth_closes = [x.get("ETHUSD", {}).get("close", 0) for x in ohlcv]
        eth_14d = self.get_return(eth_closes, 14)

        for ticker in self.tradeable_assets:
            closes = [x.get(ticker, {}).get("close", 0) for x in ohlcv]
            volumes = [x.get(ticker, {}).get("volume", 0) for x in ohlcv]
            
            # §2.4 Loser Protocol: Exit if asset drops 10% on >1.5x volume
            if len(closes) >= 20:
                recent_drop = (closes[-1] - max(closes[-10:])) / max(closes[-10:]) if max(closes[-10:]) > 0 else 0
                vol_20d_avg = sum(volumes[-20:]) / 20 if sum(volumes[-20:]) > 0 else 1
                if recent_drop <= -0.10 and volumes[-1] > (1.5 * vol_20d_avg):
                    continue 

            # §4.1 Crypto Primary Entry Anchors
            if ticker in ["BTCUSD", "ETHUSD"]:
                ema_21 = self.get_ema(closes, 21)
                macd = self.get_macd(closes)
                if closes[-1] < ema_21 or macd < 0:
                    continue # Fails primary entry confirmation
                    
            # §4.2 Altcoin Strict Gate
            if ticker in ["SOLUSD", "SUIUSD"]:
                asset_14d = self.get_return(closes, 14)
                if asset_14d <= btc_14d or asset_14d <= eth_14d:
                    continue 
            
            cms = self.calculate_cms(ticker, ohlcv, data)
            
            # §2.4 Sentiment Overlay: +2 stdev anomaly boosts viability
            social_data = data.get(("social_sentiment", ticker), [])
            if len(social_data) >= 30:
                sent_scores = [x.get("twitterSentiment", 0.5) for x in social_data[-30:]]
                sent_mean = sum(sent_scores) / 30
                sent_stdev = self.get_stdev(sent_scores)
                if sent_scores[-1] > (sent_mean + (2 * sent_stdev)):
                    cms *= 1.15 # Internal weight bump
            
            if cms != -999:
                cms_scores[ticker] = cms
                volatilities_21d[ticker] = self.get_stdev(closes[-21:])

        # =====================================================================
        # §1.3 VOLATILITY-SCALED SIZING
        # =====================================================================
        sleeves = {
            "tech": self.tech_tickers,
            "biotech": self.biotech_tickers,
            "crypto": self.crypto_tickers,
            "metals": self.metals_tickers
        }
        
        base_target_vol = 0.05
        spy_closes = [x.get("SPY", {}).get("close", 0) for x in ohlcv]
        portfolio_vol = self.get_stdev(spy_closes[-21:])
        
        if portfolio_vol > 0.08: base_target_vol *= 0.75 
        elif portfolio_vol < 0.03: base_target_vol *= 1.15 
            
        for sleeve_name, tickers in sleeves.items():
            sleeve_budget = sleeve_budgets.get(sleeve_name, 0.1)
            valid_candidates = {k: v for k, v in cms_scores.items() if k in tickers}
            
            if not valid_candidates: continue
                
            sorted_candidates = sorted(valid_candidates.items(), key=lambda x: x[1], reverse=True)
            top_candidates = sorted_candidates[:2] 
            
            for ticker, score in top_candidates:
                ticker_vol = volatilities_21d.get(ticker, 0.01)
                raw_weight = (base_target_vol / ticker_vol) * (sleeve_budget / len(top_candidates))
                
                # §8.1 Hard Constraints
                if ticker in ["SOLUSD", "SUIUSD"]: cap = 0.04 
                elif ticker in self.biotech_tickers: cap = 0.03 
                elif ticker in ["BTCUSD", "ETHUSD"]: cap = 0.10 
                else: cap = 0.07 
                    
                # §2.3 Leveraged ETF Protection
                if ticker in ["TQQQ", "SOXL", "NUGT"] and vix_regime >= 3:
                    raw_weight = 0 
                    
                target_weights[ticker] = min(raw_weight, cap)

        total_weight = sum(target_weights.values())
        if total_weight > 1.0:
            for k in target_weights:
                target_weights[k] = round(target_weights[k] / total_weight, 4)
        else:
            for k in target_weights:
                target_weights[k] = round(target_weights[k], 4)
                
        return TargetAllocation(target_weights)