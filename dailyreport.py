from datetime import datetime
import logging
import sys
from prometheus_api_client import PrometheusConnect
import requests
from config import conf
import db
from main import BAccount

prom = PrometheusConnect(url=conf["prometheus"])


def send_notify(text, channel=conf["slack_channel"]):
    try:
        # 使用代码块包裹整个消息以保持等宽对齐
        formatted_text = f"```\n{text}\n```"

        slack_result = requests.post(
            "https://slack.com/api/chat.postMessage",
            timeout=10,
            headers={
                "Authorization": conf["slack_token"],
                "Content-Type": "application/json;charset=utf-8",
            },
            json={
                "channel": channel,
                "text": formatted_text,
                "mrkdwn": True,
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
    # 立即推送并
    if leverage > 1.5:
        pass
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

    # 七日资费
    if 'exported_job' in conf:
        job_name = conf["exported_job"]
        jlp_7d_funding_query = f'jlp_7d_funding{{exported_job="{job_name}"}} * jlp_total_value{{exported_job="{job_name}"}} * 7 / 365'
        jlp_7d_funding_result = prom.custom_query(jlp_7d_funding_query)
        jlp_7d_funding = round2(jlp_7d_funding_result[0]["value"][1]) if jlp_7d_funding_result else 0
    else:
        jlp_7d_funding = 0

    from prettytable import PrettyTable

    # 账户状态摘要表格
    account_status_table = PrettyTable()
    account_status_table.field_names = ["指标", "当前值", "24h变化"]
    account_status_table.align["指标"] = "l"
    account_status_table.align["当前值"] = "r"
    account_status_table.align["24h变化"] = "r"
    account_status_table.add_row(["账户总价值", f"${tv}", f"{tvc}({tvcp}%)"])
    account_status_table.add_row(["当前杠杆率", f"{leverage}x", f"{leverage_change}"])
    account_status_table.add_row(["UniMMR", f"{unimmr}", f"{unimmr_change}"])
    account_status_table.add_row(["未实现盈亏", f"${upl}", f"{upl_change}({upl_change_pct}%)"])

    # 账户资产分布表格
    asset_distribution_table = PrettyTable()
    asset_distribution_table.field_names = ["账户类型", "资产价值", "占比", "24h变化"]
    asset_distribution_table.align["账户类型"] = "l"
    asset_distribution_table.align["资产价值"] = "r"
    asset_distribution_table.align["占比"] = "r"
    asset_distribution_table.align["24h变化"] = "r"
    asset_distribution_table.add_row(["现货账户", f"${spot_value}", f"{spot_ratio}%", f"{spot_value_change}({spot_value_change_pct}%)"])
    asset_distribution_table.add_row(["统一账户权益", f"${portfolio_value}", f"{portfolio_ratio}%", f"{portfolio_value_change}({portfolio_value_change_pct}%)"])

    # 持仓方向分析表格
    position_direction_table = PrettyTable()
    position_direction_table.field_names = ["方向", "持仓价值", "占比", "24h变化"]
    position_direction_table.align["方向"] = "l"
    position_direction_table.align["持仓价值"] = "r"
    position_direction_table.align["占比"] = "r"
    position_direction_table.align["24h变化"] = "r"
    position_direction_table.add_row(["多头总价值", f"${long_value}", f"{long_ratio}%", f"{long_value_change}({long_value_change_pct}%)"])
    position_direction_table.add_row(["空头总价值", f"${short_value}", f"{short_ratio}%", f"{short_value_change}({short_value_change_pct}%)"])
    position_direction_table.add_row(["净持仓", f"${net_value}", f"{net_ratio}%", f"{net_value_change}({net_value_change_pct}%)"])

    # 保证金状况表格
    margin_status_table = PrettyTable()
    margin_status_table.field_names = ["指标", "当前值", "24h变化"]
    margin_status_table.align["指标"] = "l"
    margin_status_table.align["当前值"] = "r"
    margin_status_table.align["24h变化"] = "r"
    margin_status_table.add_row(["可用保证金", f"${available_margin}", f"{available_margin_change}({available_margin_change_pct}%)"])
    margin_status_table.add_row(["调整后权益", f"${adjusted_margin}", f"{adjusted_margin_change}({adjusted_margin_change_pct}%)"])
    margin_status_table.add_row(["维持保证金", f"${maint_margin}", f"{maint_margin_change}({maint_margin_change_pct}%)"])
    margin_status_table.add_row(["总负债", f"${debt_value}", f"{debt_value_change}({debt_value_change_pct}%)"])
    margin_status_table.add_row(["有息负债", f"${borrowed_value}", f"{borrowed_value_change}({borrowed_value_change_pct}%)"])
    margin_status_table.add_row(["七日资费", f"${jlp_7d_funding}", "-"])

    # 风险评估表格
    risk_assessment_table = PrettyTable()
    risk_assessment_table.field_names = ["风险等级", "说明", "建议操作"]
    risk_assessment_table.align["风险等级"] = "l"
    risk_assessment_table.align["说明"] = "l"
    risk_assessment_table.align["建议操作"] = "l"
    risk_assessment_table.add_row(["🟢 低风险", ">清算线100%以上", "正常监控"])
    risk_assessment_table.add_row(["🟡 中等风险", "清算线(30%-60%)", "准备额外保证金"])
    risk_assessment_table.add_row(["🔴 高风险", "清算线(<30%)", "立即追加保证金或减仓"])

    margin_distribution = db.Margin.filter()
    margin_distribution = sorted(margin_distribution, key=lambda x: x.value, reverse=True)

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
    positions = sorted(positions, key=lambda x: x.value, reverse=True)
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
    # 按value排序
    spot_positions = sorted(spot_positions, key=lambda x: x.value, reverse=True)
    spot_positions_table = PrettyTable()
    spot_positions_table.field_names = ["币种", "数量", "价格", "价值"]
    for p in spot_positions:
        if p.value < 100:
            continue
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
        "jlp_7d_funding": jlp_7d_funding,
        "account_status_table": account_status_table,
        "asset_distribution_table": asset_distribution_table,
        "position_direction_table": position_direction_table,
        "margin_status_table": margin_status_table,
        "risk_assessment_table": risk_assessment_table,
        "margin_distribution": margin_distribution_table,
        "positions": positions_table,
        "spot_positions": spot_positions_table,
        "orders_table": orders_table,
    }
    return template.render(vars)


if __name__ == "__main__":
    send_notify(render_report(sys.argv[1]))
