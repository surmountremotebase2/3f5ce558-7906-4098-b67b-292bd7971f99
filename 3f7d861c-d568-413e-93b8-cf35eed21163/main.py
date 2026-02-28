#Type code here
from surmount.base_class import Strategy, TargetAllocation
from surmount.data import InstitutionalOwnership, InsiderTrading, SocialSentiment
import math

class TradingStrategy(Strategy):
    def __init__(self):
        # §2-5 UNIVERSES: Pre-selecting compliant assets satisfying fundamental velocity & liquidity
        self.tech_tickers = ["NVDA", "AVGO", "PLTR", "TQQQ", "SOXL"]
        self.biotech_tickers = ["XBI", "CRSP", "VRTX", "NVO"]
        self.crypto_tickers = ["BTC", "ETH", "SOL", "SUI"]
        self.metals_tickers = ["GLD", "SLV", "FNV", "NUGT"]
        
        # §6 MACRO REGIME TICKERS: Proxies for dynamic scaling (VIX, DXY via UUP, SPY for baseline)
        self.macro_tickers = ["VIXY", "UUP", "SPY"] 
        
        self.tickers = self.tech_tickers + self.biotech_tickers + self.crypto_tickers + self.metals_tickers + self.macro_tickers
        
        # Initialize alternative data arrays for CMS component calculations
        self.data_list = []
        for ticker in self.tickers:
            self.data_list.append(SocialSentiment(ticker))
            self.data_list.append(InstitutionalOwnership(ticker))
            self.data_list.append(InsiderTrading(ticker))

    @property
    def interval(self):
        # §1.1 Tactical horizon optimization (daily frequency for shorter term reactivity)
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    # =====================================================================
    # INTERNAL ROBUST INDICATORS (Bypasses Surmount Library KeyErrors)
    # =====================================================================
    def get_sma(self, prices, length):
        """Robust SMA calculation to prevent library errors on missing data."""
        valid_prices = [p for p in prices if p > 0]
        if len(valid_prices) < length or length < 1:
            return 0.01
        return sum(valid_prices[-length:]) / length

    def get_stdev(self, prices, length):
        """Robust STDEV calculation to prevent library errors on missing data."""
        valid_prices = [p for p in prices if p > 0]
        if len(valid_prices) < length or length < 2:
            return 0.01
        window = valid_prices[-length:]
        mean = sum(window) / length
        variance = sum((x - mean) ** 2 for x in window) / length
        return math.sqrt(variance) if variance > 0 else 0.01

    def run(self, data):
        ohlcv = data.get("ohlcv", [])
        
        # Require sufficient lookback for the 50-day volume and DXY metrics
        if len(ohlcv) < 50:
            return TargetAllocation({})
            
        target_weights = {}

        # =====================================================================
        # §6 REGIME DETECTION & CROSS-SLEEVE INTELLIGENCE
        # =====================================================================
        
        # 6.1 VIX-Based Volatility Regime System
        vix_prices = [x.get("VIXY", {}).get("close", 0) for x in ohlcv]
        vix_sma_5 = self.get_sma(vix_prices, 5)
        
        # 6.2 DXY-Based Currency Regime Overlay (Using UUP as US Dollar Proxy)
        uup_closes = [x.get("UUP", {}).get("close", 0) for x in ohlcv]
        uup_sma_50 = self.get_sma(uup_closes, 50)
        
        # Safely extract last valid UUP close
        uup_valid = [p for p in uup_closes if p > 0]
        last_uup = uup_valid[-1] if uup_valid else 0
        dollar_weakening = last_uup < uup_sma_50 and last_uup > 0
        
        # Base Allocation Bands
        sleeve_budgets = {
            "tech": 0.30,
            "biotech": 0.17,
            "crypto": 0.28,
            "metals": 0.12,
        }
        
        # Dynamic Master Risk Overlay Adjustments
        vix_regime = 1
        if vix_sma_5 >= 30:   # Regime 4: Crisis Volatility
            vix_regime = 4
            sleeve_budgets["tech"] = 0.20
            sleeve_budgets["crypto"] = 0.20
            sleeve_budgets["biotech"] = 0.12
            sleeve_budgets["metals"] = 0.20
        elif vix_sma_5 >= 25: # Regime 3: High Volatility
            vix_regime = 3
            sleeve_budgets["tech"] -= 0.05
            sleeve_budgets["crypto"] -= 0.03
            sleeve_budgets["metals"] += 0.05
        elif vix_sma_5 >= 18: # Regime 2: Elevated Volatility
            vix_regime = 2
            sleeve_budgets["metals"] += 0.02
            
        if dollar_weakening:
            sleeve_budgets["metals"] += 0.03
        else:
            sleeve_budgets["metals"] -= 0.03

        # =====================================================================
        # §1.2 MOMENTUM SIGNAL CONSTRUCTION (CMS) & FILTER A
        # =====================================================================
        cms_scores = {}
        volatilities_21d = {}
        
        for ticker in self.tickers:
            if ticker in self.macro_tickers: 
                continue
            
            closes = [x.get(ticker, {}).get("close", 0) for x in ohlcv]
            volumes = [x.get(ticker, {}).get("volume", 0) for x in ohlcv]
            
            # Crash Prevention: Avoid divide-by-zero or insufficient data by mandating valid positive pricing
            if len(closes) < 50 or closes[-1] <= 0 or closes[-6] <= 0 or closes[-48] <= 0 or closes[-13] <= 0:
                continue
                
            # Filter A (Absolute Momentum) & Skip-Day Rule (Excluding most recent 5 days)
            # Comparing day -6 vs day -48 yields a true 42-day window pre-lag
            skip_day_return = (closes[-6] - closes[-48]) / closes[-48]
            
            if skip_day_return <= 0:
                continue # Fails absolute time-series momentum gate
                
            # Component 1: Risk-Adjusted 12-day return (30%)
            ret_12d = (closes[-1] - closes[-13]) / closes[-13]
            vol_12d = self.get_stdev(closes, 12)
            risk_adj_ret = ret_12d / vol_12d
            
            # Cache 21-day volatility for Position Sizing (§1.3)
            volatilities_21d[ticker] = self.get_stdev(closes, 21)

            # Component 3: Sentiment Acceleration (20%)
            social_data = data.get(("social_sentiment", ticker), [])
            sent_accel = 0
            if len(social_data) >= 20:
                sent_5 = sum([x.get("twitterSentiment", 0.5) for x in social_data[-5:]]) / 5
                sent_20 = sum([x.get("twitterSentiment", 0.5) for x in social_data[-20:]]) / 20
                sent_accel = sent_5 - sent_20

            # Component 4: Institutional Flow / Insider Signal (15%)
            inst_signal = 0
            insider_data = data.get(("insider_trading", ticker), [])
            
            # Corrected SEC Form 4 text processing
            if len(insider_data) > 0:
                last_type = insider_data[-1].get("transactionType", "").lower()
                if "buy" in last_type or "purchase" in last_type:
                    inst_signal += 1
                    
            inst_own_data = data.get(("institutional_ownership", ticker), [])
            if len(inst_own_data) > 0 and inst_own_data[-1].get("increasedPositionsChange", 0) > 0:
                inst_signal += 1

            # Component 5: Volume Confirmation Ratio (10%)
            vol_10 = sum(volumes[-10:]) / 10
            vol_50 = sum(volumes[-50:]) / 50
            vol_ratio = vol_10 / vol_50 if vol_50 > 0 else 1
            
            # Composite Momentum Score Formula
            cms = (0.30 * risk_adj_ret) + \
                  (0.25 * skip_day_return) + \
                  (0.20 * sent_accel) + \
                  (0.15 * inst_signal) + \
                  (0.10 * vol_ratio)
                  
            cms_scores[ticker] = cms

        # =====================================================================
        # §1.3 & §8 VOLATILITY-SCALED POSITION SIZING & RELATIVE MOMENTUM
        # =====================================================================
        sleeves = {
            "tech": self.tech_tickers,
            "biotech": self.biotech_tickers,
            "crypto": self.crypto_tickers,
            "metals": self.metals_tickers
        }
        
        # Bongaerts et al. Conditional Enhancement (Baseline Vol = 5%)
        base_target_vol = 0.05
        spy_closes = [x.get("SPY", {}).get("close", 0) for x in ohlcv]
        portfolio_vol = self.get_stdev(spy_closes, 21)
        
        if portfolio_vol > 0.08:
            base_target_vol *= 0.75 # Reduce portfolio leverage
        elif portfolio_vol < 0.03:
            base_target_vol *= 1.15 # Increase portfolio leverage
            
        for sleeve_name, tickers in sleeves.items():
            sleeve_budget = sleeve_budgets.get(sleeve_name, 0.1)
            # Valid candidates passed Absolute Momentum gate
            valid_candidates = {k: v for k, v in cms_scores.items() if k in tickers}
            
            if not valid_candidates:
                continue
                
            # Filter B: Relative Cross-Sectional Momentum (Select the strongest performers)
            sorted_candidates = sorted(valid_candidates.items(), key=lambda x: x[1], reverse=True)
            
            # Select top 2 names per sleeve to balance concentration vs. diversification
            top_candidates = sorted_candidates[:2]
            
            for ticker, score in top_candidates:
                # 1.3 Barroso & Santa-Clara Inverse Volatility Sizing
                ticker_vol = volatilities_21d.get(ticker, 0.01)
                
                # Formula: Weight = (Target_Vol / RealizedVol_21d) * Base_Weight
                raw_weight = (base_target_vol / ticker_vol) * (sleeve_budget / len(top_candidates))
                
                # §8.1 Hard Constraints & Caps
                if ticker in self.crypto_tickers and ticker not in ["BTC", "ETH"]:
                    cap = 0.04 # Max individual altcoin
                elif ticker in self.biotech_tickers:
                    cap = 0.03 # Max individual biotech (Binary Event Limit)
                elif ticker in ["BTC", "ETH"]:
                    cap = 0.10 # Max major crypto
                else:
                    cap = 0.07 # Max single equity
                    
                # §2.3 / §5.1 Leveraged ETF variance drain & Volatility protection
                if ticker in ["TQQQ", "SOXL", "NUGT"] and vix_regime >= 3:
                    raw_weight = 0 # Exit ALL leveraged ETF positions during VIX > 25/30
                    
                target_weights[ticker] = min(raw_weight, cap)

        # Normalize total weights to ensure systemic 100% capacity adherence
        # We explicitly round down to 4 decimals to avoid 1.00000000000002 allocation rejections
        total_weight = sum(target_weights.values())
        if total_weight > 1.0:
            for k in target_weights:
                target_weights[k] = round(target_weights[k] / total_weight, 4)
        else:
            for k in target_weights:
                target_weights[k] = round(target_weights[k], 4)
                
        return TargetAllocation(target_weights)