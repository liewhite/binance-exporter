from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from config import conf


registry = CollectorRegistry()

############################### 账户状态摘要 ###############################
total_value = Gauge(
    "cex_total_value",
    "Total value of the account",
    labelnames=["account"],
    registry=registry,
)

leverage = Gauge(
    "cex_leverage",
    "Leverage of the account",
    labelnames=["account"],
    registry=registry,
)

unimmr = Gauge(
    "cex_unimmr",
    "Unimmr of the account",
    labelnames=["account"],
    registry=registry,
)

upl = Gauge(
    "cex_upl",
    "Unrealized P/L of the account",
    labelnames=["account"],
    registry=registry,
)

############################### 资产汇总  ###############################
### 账户资产分布
asset_distribution = Gauge(
    "cex_asset_distribution",
    "Distribution of the account assets",
    labelnames=["account","name"], # name: spot,portfolio,upl
    registry=registry,
)
### 持仓方向分析
position_overview = Gauge(
    "cex_position_overview",
    "Overview of the account positions",
    labelnames=["account","name"], # name: long,short,net
    registry=registry,
)
## 🔍 统一账户详情
### 保证金状况
margin_status = Gauge(
    "cex_margin_status",
    "Status of the account margin",
    labelnames=["account","name"], # name: debt,maint,available,adjusted_eq
    registry=registry,
)
### 保证金分布
margin_distribution = Gauge(
    "cex_margin_distribution",
    "Distribution of the account margin",
    labelnames=["account", "token", "column"], # column: amt, value, collateral_ratio, collateral_value
    registry=registry,
)

### ADL数量
margin_adl = Gauge(
    "cex_adl",
    "Status of the account adl",
    labelnames=["account","symbol"], # name: debt,maint,available,adjusted_eq
    registry=registry,
)

def push(name):
    push_to_gateway(
        conf['pushgateway'],
        job=f"cextest-{name}",
        registry=registry,
    )







