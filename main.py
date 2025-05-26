from datetime import datetime
import json
import sys
import time
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from config import conf
import metrics
import db


class BAccount:
    def __init__(self, ak, sk, name):
        self.name = name
        self.client = Client(ak, sk)

    def get_prices(self):
        tickers = self.client.get_all_tickers()
        prices = {
            i["symbol"][:-4]: float(i["price"])
            for i in tickers
            if i["symbol"].endswith("USDT")
        }
        prices["USDT"] = 1
        prices["USDC"] = 1
        prices["FDUSD"] = 1
        return prices

    def get_spot_account(self):
        return self.client.get_account()

    def get_spot_account_eq(self, acc, prices):
        eq = 0
        for i in acc["balances"]:
            free = float(i["free"])
            locked = float(i["locked"])
            if i["asset"] == "USDT" or i["asset"] == "USDC" or i["asset"] == "FDUSD":
                eq += free + locked
                continue
            amt = free + locked
            if amt > 0.0001:
                eq += amt * prices.get(i["asset"], 0)
        return eq

    def get_portfolio_account(self):
        return self.client.papi_get_account()

    def uniMMR(self, acc):
        return float(acc["uniMMR"])

    def portfolio_eq(self, acc):
        return float(acc["actualEquity"])

    def portfolio_adjusted_eq(self, acc):
        return float(acc["accountEquity"])

    def portfolio_maint_margin(self, acc):
        return float(acc["accountMaintMargin"])

    def portfolio_available_balance(self, acc):
        return float(acc["totalAvailableBalance"])

    def portfolio_um_account(self):
        return self.client.papi_get_um_account_v2()

    def portfolio_account_debt(self, acc, prices):
        debt = 0
        for i in acc:
            debt += (
                float(i["negativeBalance"]) + float(i["crossMarginInterest"])
            ) * prices.get(i["asset"], 0)
        return debt

    def portfolio_borrowed(self, acc, prices):
        """
        有息负债
        """
        debt = 0
        for i in acc:
            if float(i["crossMarginBorrowed"]) != 0:
                debt += float(i["crossMarginBorrowed"]) * prices.get(i["asset"], 0)
        return debt

    def positions(self):
        return self.client.papi_get_um_position_risk()

    def long_positions(self, positions):
        return [i for i in positions if float(i["positionAmt"]) > 0]

    def short_positions(self, positions):
        return [i for i in positions if float(i["positionAmt"]) < 0]

    def long_positions_notional(self, positions):
        return sum([abs(float(i["notional"])) for i in self.long_positions(positions)])

    def short_positions_notional(self, positions):
        return sum([abs(float(i["notional"])) for i in self.short_positions(positions)])

    def net_positions_notional(self, positions):
        return self.long_positions_notional(positions) - self.short_positions_notional(
            positions
        )

    def positions_notional(self, positions):
        return sum([abs(float(i["notional"])) for i in positions])

    def positions_upl(self, positions):
        return sum([float(i["unRealizedProfit"]) for i in positions])


def update_metrics(ba: BAccount, prices):
    name = ba.name
    spot_account = ba.get_spot_account()
    portfolio_account = ba.get_portfolio_account()
    portfolio_um_account = ba.portfolio_um_account()

    # 账户状态摘要
    total_value = ba.get_spot_account_eq(spot_account, prices) + ba.portfolio_eq(
        portfolio_account
    )
    positions = ba.positions()
    positions_value = ba.positions_notional(positions)
    leverage = positions_value / ba.portfolio_adjusted_eq(portfolio_account)
    metrics.total_value.labels(name).set(total_value)
    metrics.leverage.labels(name).set(leverage)
    metrics.unimmr.labels(name).set(ba.uniMMR(portfolio_account))
    metrics.upl.labels(name).set(ba.positions_upl(positions))

    # 资产汇总
    metrics.asset_distribution.labels(name, "spot").set(
        ba.get_spot_account_eq(spot_account, prices)
    )
    metrics.asset_distribution.labels(name, "portfolio").set(
        ba.portfolio_eq(portfolio_account)
    )
    ### 持仓方向分析
    metrics.position_overview.labels(name, "long").set(
        ba.long_positions_notional(positions)
    )
    metrics.position_overview.labels(name, "short").set(
        ba.short_positions_notional(positions)
    )
    metrics.position_overview.labels(name, "net").set(
        ba.net_positions_notional(positions)
    )
    ## 🔍 统一账户详情
    ### 保证金状况
    metrics.margin_status.labels(name, "available").set(
        ba.portfolio_available_balance(portfolio_account)
    )
    metrics.margin_status.labels(name, "adjusted_eq").set(
        ba.portfolio_adjusted_eq(portfolio_account)
    )
    metrics.margin_status.labels(name, "maint").set(
        ba.portfolio_maint_margin(portfolio_account)
    )
    account_balances = ba.client.margin_v1_get_portfolio_balance()
    # 总债务
    metrics.margin_status.labels(name, "debt").set(
        ba.portfolio_account_debt(account_balances, prices)
    )
    # 有息负债
    metrics.margin_status.labels(name, "borrowed").set(
        ba.portfolio_borrowed(account_balances, prices)
    )
    metrics.push(name)


def update_db(positions, spot_acc, margin_distribution, prices, orders, spot_orders):
    # 更新订单和持仓
    with db.db.atomic():
        db.Position.delete().execute()
        db.Spot.delete().execute()
        db.Margin.delete().execute()
        db.Order.delete().execute()

        for position in positions:
            amt = float(position["positionAmt"])
            side = "long" if amt > 0 else "short"
            db.Position(
                symbol=position["symbol"],
                direction=side,
                amount=abs(amt),
                value=abs(float(position["notional"])),
                entry_price=float(position.get("entryPrice", 0)),
                price=float(position.get("markPrice", 0)),
                liq_price=float(position.get("liquidationPrice", 0)),
                funding_rate=0,  # todo
                upl=float(position.get("unRealizedProfit", 0)),
            ).save()
        for i in spot_acc["balances"]:
            price = prices.get(i["asset"], 0)
            amt = float(i["free"]) + float(i["locked"])
            if amt != 0:
                db.Spot(
                    token=i["asset"],
                    amount=amt,
                    price=price,
                    value=amt * price,
                ).save()
        for i in margin_distribution:
            asset = i["asset"]
            eq = (
                float(i["totalWalletBalance"])
                + float(i["umUnrealizedPNL"])
                - float(i["crossMarginInterest"])
            )
            db.Margin(
                token=asset,
                amount=eq,
                value=eq * prices.get(asset, 0),
                collateral_ratio=0,
                collateral_value=0,
            ).save()

        now = time.time() * 1000
        long_orders = {}
        short_orders = {}
        for o in orders:
            if o["time"] < now - 1000 * 60 * 60 * 24:
                continue
            if o["status"] == "FILLED" or o["status"] == "PARTIALLY_FILLED":
                symbol = o["symbol"]
                price = float(o["avgPrice"])
                qty = float(o["executedQty"])

                if o["side"] == "BUY":
                    if symbol not in long_orders:
                        long_orders[symbol] = {
                            "symbol": symbol,
                            "amount": 0,
                            "value": 0,
                        }
                    long_orders[symbol]["amount"] += qty
                    long_orders[symbol]["value"] += qty * price
                else:
                    if symbol not in short_orders:
                        short_orders[symbol] = {
                            "symbol": symbol,
                            "amount": 0,
                            "value": 0,
                        }
                    short_orders[symbol]["amount"] += qty
                    short_orders[symbol]["value"] += qty * price

        for k, v in long_orders.items():
            v["price"] = v["value"] / v["amount"]
        for k, v in short_orders.items():
            v["price"] = v["value"] / v["amount"]

        for o in long_orders.values():
            db.Order(
                symbol=o["symbol"],
                market="future",
                direction="long",
                amount=abs(o["amount"]),
                price=o["price"],
                value=abs(o["value"]),
            ).save()

        for o in short_orders.values():
            db.Order(
                symbol=o["symbol"],
                market="future",
                direction="short",
                amount=abs(o["amount"]),
                price=o["price"],
                value=abs(o["value"]),
            ).save()

        long_orders = {}
        short_orders = {}
        for o in spot_orders:
            if o["time"] < now - 1000 * 60 * 60 * 24:
                continue
            if o["status"] == "FILLED" or o["status"] == "PARTIALLY_FILLED":
                symbol = o["symbol"]
                price = float(o["avgPrice"])
                qty = float(o["executedQty"])

                if o["side"] == "BUY":
                    if symbol not in long_orders:
                        long_orders[symbol] = {
                            "symbol": symbol,
                            "amount": 0,
                            "value": 0,
                        }
                    long_orders[symbol]["amount"] += qty
                    long_orders[symbol]["value"] += qty * price
                else:
                    if symbol not in short_orders:
                        short_orders[symbol] = {
                            "symbol": symbol,
                            "amount": 0,
                            "value": 0,
                        }
                    short_orders[symbol]["amount"] += qty
                    short_orders[symbol]["value"] += qty * price

        for k, v in long_orders.items():
            v["price"] = v["value"] / v["amount"]
        for k, v in short_orders.items():
            v["price"] = v["value"] / v["amount"]

        for o in long_orders.values():
            db.Order(
                symbol=o["symbol"],
                market="spot",
                direction="buy",
                amount=abs(o["amount"]),
                price=o["price"],
                value=abs(o["value"]),
            ).save()

        for o in short_orders.values():
            db.Order(
                symbol=o["symbol"],
                market="spot",
                direction="sell",
                amount=abs(o["amount"]),
                price=o["price"],
                value=abs(o["value"]),
            ).save()


def main():
    while True:
        ba = BAccount(conf["ak"], conf["sk"], conf["name"])
        prices = ba.get_prices()
        update_metrics(ba, prices)
        positions = ba.positions()
        spot_account = ba.get_spot_account()
        margin_distribution = ba.client.margin_v1_get_portfolio_balance()
        orders = ba.client.papi_get_um_all_orders()
        # 必须传入symbol， 有点费劲
        # spot_orders = ba.client.get_all_orders()
        spot_orders = []
        update_db(
            positions, spot_account, margin_distribution, prices, orders, spot_orders
        )
        time.sleep(30)


if __name__ == "__main__":
    # ba = BAccount(conf["ak"], conf["sk"], conf["name"])
    # print(ba.client.get_cross_margin_collateral_ratio())
    # print(ba.client.margin_v1_get_portfolio_balance())
    main()
