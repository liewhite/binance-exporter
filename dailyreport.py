from datetime import datetime
import logging
import sys
from prometheus_api_client import PrometheusConnect
import requests
from config import conf
import db

prom = PrometheusConnect(url=conf["prometheus"])


def send_notify(text, channel=conf["slack_channel"]):
    try:
        slack_result = requests.post(
            "https://slack.com/api/chat.postMessage",
            timeout=10,
            headers={
                "Authorization": conf["slack_token"],
                "Content-Type": "application/json;charset=utf-8",
            },
            json={
                "channel": channel,
                "text": text,
            },
        )
        logging.info(f"slack result: {slack_result.status_code}, {slack_result.text}")
    except Exception as e:
        logging.warn(f"failed send slack {e}")


def round2(x):
    return round(float(x), 2)


def total_value(account_name):
    query = f'cex_total_value{{account="{account_name}"}}'
    result = prom.custom_query(query)
    return round2(result[0]["value"][1])


def total_value_change(account_name):
    query = f'delta(cex_total_value{{account="{account_name}"}}[1d])'
    result = prom.custom_query(query)
    return round2(result[0]["value"][1])


def render_report(account_name):
    from jinja2 import Template

    prom = PrometheusConnect(url=conf["prometheus"])
    date = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H:%M:%S")
    template = Template(open("template.txt").read())

    tv = total_value(account_name)
    tvc = total_value_change(account_name)
    tvcp = round2(tvc / tv * 100)

    leverage = round2(
        prom.custom_query(f'cex_leverage{{account="{account_name}"}}')[0]["value"][1]
    )
    leverage_change = round2(
        prom.custom_query(f'delta(cex_leverage{{account="{account_name}"}}[1d])')[0][
            "value"
        ][1]
    )
    unimmr = round2(
        prom.custom_query(f'cex_unimmr{{account="{account_name}"}}')[0]["value"][1]
    )
    unimmr_change = round2(
        prom.custom_query(f'delta(cex_unimmr{{account="{account_name}"}}[1d])')[0][
            "value"
        ][1]
    )
    upl = round2(
        prom.custom_query(f'cex_upl{{account="{account_name}"}}')[0]["value"][1]
    )
    upl_change = round2(
        prom.custom_query(f'delta(cex_upl{{account="{account_name}"}}[1d])')[0][
            "value"
        ][1]
    )

    upl_change_pct = round2(upl_change / tv) * 100

    spot_value = round2(
        prom.custom_query(
            f'cex_asset_distribution{{account="{account_name}", name="spot"}}'
        )[0]["value"][1]
    )
    spot_value_change = round2(
        prom.custom_query(
            f'delta(cex_asset_distribution{{account="{account_name}", name="spot"}}[1d])'
        )[0]["value"][1]
    )

    spot_value_change_pct = (
        round2(spot_value_change / spot_value) if spot_value != 0 else 0
    ) * 100

    portfolio_value = round2(
        prom.custom_query(
            f'cex_asset_distribution{{account="{account_name}", name="portfolio"}}'
        )[0]["value"][1]
    )
    portfolio_value_change = round2(
        prom.custom_query(
            f'delta(cex_asset_distribution{{account="{account_name}", name="portfolio"}}[1d])'
        )[0]["value"][1]
    )
    portfolio_value_change_pct = round2(portfolio_value_change / portfolio_value) * 100

    spot_ratio = round2(spot_value / (spot_value + portfolio_value)) * 100
    portfolio_ratio = round2(portfolio_value / (spot_value + portfolio_value)) * 100

    long_value = round2(
        prom.custom_query(
            f'cex_position_overview{{account="{account_name}", name="long"}}'
        )[0]["value"][1]
    )
    long_value_change = round2(
        prom.custom_query(
            f'delta(cex_position_overview{{account="{account_name}", name="long"}}[1d])'
        )[0]["value"][1]
    )
    long_value_change_pct = (
        round2(long_value_change / long_value) * 100 if long_value != 0 else 0
    )
    long_ratio = round2(long_value / portfolio_value) * 100

    short_value = round2(
        prom.custom_query(
            f'cex_position_overview{{account="{account_name}", name="short"}}'
        )[0]["value"][1]
    )
    short_value_change = round2(
        prom.custom_query(
            f'delta(cex_position_overview{{account="{account_name}", name="short"}}[1d])'
        )[0]["value"][1]
    )
    short_value_change_pct = (
        round2(short_value_change / short_value) * 100 if short_value != 0 else 0
    )
    short_ratio = round2(short_value / portfolio_value) * 100

    net_value = round2(
        prom.custom_query(
            f'cex_position_overview{{account="{account_name}", name="net"}}'
        )[0]["value"][1]
    )
    net_value_change = round2(
        prom.custom_query(
            f'delta(cex_position_overview{{account="{account_name}", name="net"}}[1d])'
        )[0]["value"][1]
    )
    net_value_change_pct = (
        round2(net_value_change / net_value) * 100 if net_value != 0 else 0
    )
    net_ratio = round2(net_value / portfolio_value) * 100

    # 保证金状况
    available_margin = round2(
        prom.custom_query(
            f'cex_margin_status{{account="{account_name}", name="available"}}'
        )[0]["value"][1]
    )
    available_margin_change = round2(
        prom.custom_query(
            f'delta(cex_margin_status{{account="{account_name}", name="available"}}[1d])'
        )[0]["value"][1]
    )
    available_margin_change_pct = (
        round2(available_margin_change / available_margin) * 100
        if available_margin != 0
        else 0
    )
    adjusted_margin = round2(
        prom.custom_query(
            f'cex_margin_status{{account="{account_name}", name="adjusted_eq"}}'
        )[0]["value"][1]
    )
    adjusted_margin_change = round2(
        prom.custom_query(
            f'delta(cex_margin_status{{account="{account_name}", name="adjusted_eq"}}[1d])'
        )[0]["value"][1]
    )
    adjusted_margin_change_pct = (
        round2(adjusted_margin_change / adjusted_margin) * 100
        if adjusted_margin != 0
        else 0
    )
    maint_margin = round2(
        prom.custom_query(
            f'cex_margin_status{{account="{account_name}", name="maint"}}'
        )[0]["value"][1]
    )
    maint_margin_change = round2(
        prom.custom_query(
            f'delta(cex_margin_status{{account="{account_name}", name="maint"}}[1d])'
        )[0]["value"][1]
    )
    maint_margin_change_pct = (
        round2(maint_margin_change / maint_margin) * 100 if maint_margin != 0 else 0
    )

    debt_value = round2(
        prom.custom_query(
            f'cex_margin_status{{account="{account_name}", name="debt"}}'
        )[0]["value"][1]
    )
    debt_value_change = round2(
        prom.custom_query(
            f'delta(cex_margin_status{{account="{account_name}", name="debt"}}[1d])'
        )[0]["value"][1]
    )
    debt_value_change_pct = (
        round2(debt_value_change / debt_value) * 100 if debt_value != 0 else 0
    )

    borrowed_value = round2(
        prom.custom_query(
            f'cex_margin_status{{account="{account_name}", name="borrowed"}}'
        )[0]["value"][1]
    )
    borrowed_value_change = round2(
        prom.custom_query(
            f'delta(cex_margin_status{{account="{account_name}", name="borrowed"}}[1d])'
        )[0]["value"][1]
    )
    borrowed_value_change_pct = (
        round2(borrowed_value_change / borrowed_value) * 100
        if borrowed_value != 0
        else 0
    )

    from prettytable import PrettyTable

    margin_distribution = db.Margin.filter()
    margin_distribution_table = PrettyTable()
    margin_distribution_table.field_names = [
        "币种",
        "数量",
        "价值",
        "抵押率",
        "抵押后价值($)",
        "负余额阈值",
        "最大负余额",
    ]
    for m in margin_distribution:
        margin_distribution_table.add_row([m.token, m.amount, m.value, 0, 0, 0, 0])

    positions = db.Position.filter()
    positions_table = PrettyTable()
    positions_table.field_names = [
        "合约",
        "方向",
        "数量",
        "价值",
        "开仓价格",
        "当前价格",
        "资金费率",
        "盈亏$",
        "盈亏%",
        "清算价格",
        "距清算",
    ]
    for p in positions:
        positions_table.add_row(
            [
                p.symbol,
                p.direction,
                p.amount,
                p.value,
                p.entry_price,
                p.price,
                0,
                p.upl,
                round(p.upl / p.value * 100, 2),
                p.liq_price,
                round((p.liq_price - p.price) / p.price * 100, 2),
            ]
        )

    spot_positions = db.Spot.filter()
    spot_positions_table = PrettyTable()
    spot_positions_table.field_names = ["币种", "数量", "价格", "价值"]
    for p in spot_positions:
        spot_positions_table.add_row([p.token, p.amount, p.price, p.value])

    orders = db.Order.filter()
    orders_table = PrettyTable()
    orders_table.field_names = ["合约", "方向", "数量", "均价", "价值"]
    for o in orders:
        orders_table.add_row([o.symbol, o.direction, o.amount, o.price, o.value])

    vars = {
        "account_name": account_name,
        "date": date,
        "time": time,
        "total_value": tv,
        "total_value_change": tvc,
        "total_value_change_pct": tvcp,
        "leverage": leverage,
        "leverage_change": leverage_change,
        "unimmr": unimmr,
        "unimmr_change": unimmr_change,
        "upl": upl,
        "upl_change": upl_change,
        "upl_change_pct": upl_change_pct,
        "spot_value": spot_value,
        "spot_value_change": spot_value_change,
        "spot_value_change_pct": spot_value_change_pct,
        "spot_ratio": spot_ratio,
        "portfolio_value": portfolio_value,
        "portfolio_value_change": portfolio_value_change,
        "portfolio_value_change_pct": portfolio_value_change_pct,
        "portfolio_ratio": portfolio_ratio,
        "long_value": long_value,
        "long_change": long_value_change,
        "long_change_pct": long_value_change_pct,
        "long_ratio": long_ratio,
        "short_value": short_value,
        "short_change": short_value_change,
        "short_change_pct": short_value_change_pct,
        "short_ratio": short_ratio,
        "net_value": net_value,
        "net_change": net_value_change,
        "net_change_pct": net_value_change_pct,
        "net_ratio": net_ratio,
        "available_margin": available_margin,
        "available_margin_change": available_margin_change,
        "available_margin_change_pct": available_margin_change_pct,
        "adjusted_margin": adjusted_margin,
        "adjusted_margin_change": adjusted_margin_change,
        "adjusted_margin_change_pct": adjusted_margin_change_pct,
        "maint_margin": maint_margin,
        "maint_margin_change": maint_margin_change,
        "maint_margin_change_pct": maint_margin_change_pct,
        "debt_value": debt_value,
        "debt_value_change": debt_value_change,
        "debt_value_change_pct": debt_value_change_pct,
        "borrowed_value": borrowed_value,
        "borrowed_value_change": borrowed_value_change,
        "borrowed_value_change_pct": borrowed_value_change_pct,
        "margin_distribution": margin_distribution_table,
        "positions": positions_table,
        "spot_positions": spot_positions_table,
        "orders_table": orders_table,
    }
    return template.render(vars)


if __name__ == "__main__":
    send_notify(render_report(sys.argv[1]))
